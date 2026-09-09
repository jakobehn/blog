---
title: TFS 2010 – Managing Build Agents using the API
date: 2009-12-08T20:47:52Z
slug: tfs-2010-managing-build-agents-using-the-api
categories: [TFS API, TFS Build, Visual Studio 2010]
aliases: [/2009/12/tfs-2010-managing-build-agents-using-the-api/]
---

In previous versions of TFS, you installed TFS Team Build on the build server and you got one build service agent. It was/is possible to start several build agents on the same server, but it is a bit of a mess. \
In addition, for each team project TFS 2008 build service can only execute one at a time (Note that builds from different team project can execute in parallell, a lot of people still don’t know this)

In TFS 2010, the concept of build controllers were introduced. A build controller belongs to one (1) project collection and is responsible of managing a set of build agents, thereby enabling a build agent pool which allows for builds to execute in parallel, even in the same team project.

The build controller also have features for selecting an appropriate build agent for a particular build. For example you can assign a set of **tags** to a build agent. A tag is just a string, and typically relate to some configuration/environment that is present on the machine of the build agent. For example you might have one build agent that builds BizTalk server projects, for which you need to install the appropriate tools on that machine. Then you tag the build definitions that build biztalk projects with the corresponding tag. This will cause the build controller to select the appropriate build agent.

You can of course have several buiuld agents with the same tag(s), thereby creating a build pool that will enable parallall builds for this type of projects as well.

By default, when installing/upgrading to TFS 2010 you will configure one 1 build controller and 1 build agent. As said before, the build agent no longer has any dependency to a team project. This means that if you have one build agent **all** builds for that project collection will be queued on the same build agent and the will not run in parallell. To enable parallell builds, open the TFS Administration Console in the build server and create one (or several) new build agent for the controller. By default, the controller will first try to find a build agent that is free and queue the build on that build agent. If all build agents are busy, the build will just be queued on the build agent with the smallest queue.

At our company, we have some builds (from TFS 2008) that actually have a problem with running in parallell with other builds. For example, some builds creates a SQL database during the build to be able to execute integration tests as part of the build. The same scripts are used by the developer to create a local sandbox environment on their development machines. The problem here we typically have several builds for the same project (CI, Nightly, Release) and all of these will create the same database as part of the build. If two of these builds would run in parallell, you can easily imagine some weird errors that would occur!

To resolve this, we can use the tag functionality, to map these build definitions to the same build agent. This will cause these builds to be executed in sequence. Since we have a lot of team project and a lot of build definitions, this require some extra management. Both to create new build agents for a new team project with the corresponding tag and to assign the same tag to the builds in the team project.

To show how this can be done using the API, I wrote a small application that runs through all team projects on a given TFS project collection. For each team project, it checks if there is a corresponding build agent with the same name. If not, the agent is created and a tag with the same name as the team project is assigned to the build agent.

Next, it runs through all build definitions for each team project and assign the corresponding tag to those builds. It is a command line tool, so we can run this on a scheduled basis to keep all build agents and build definitions in sync. You will see from the sample that using the TFS API is very simple and intuitive. The only exception here was to read and modify the Tags property for a build definition. This is stored instide the Agent Settings object which is stored as a serialized dictionary. There is rather ugly code to access this information, this could probably be done differently.

Here is the code, enjoy :-)

```csharp
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using Microsoft.TeamFoundation.Server;
using Microsoft.TeamFoundation.Build.Client;
using Microsoft.TeamFoundation.VersionControl.Client;
using Microsoft.TeamFoundation.Client;
using System.Xml.Serialization;
using System.IO;
using System.Xml.Linq;

namespace TFSBuildAgentManager
{
    class TFSBuildAgentManager
    {
        private static string BuildAgentWorkingDirectory = @"D:Build$(BuildAgentId)$(BuildDefinitionPath)";

        static void Main(string[] args)
        {
            if (args.Length != 1 && args.Length != 2)
            {
                Console.WriteLine("Usage: TFSBuildAgentManager.exe tfsServerUrl [buildAgentWorkingDirectory]");
                return;
            }

            string tfsServer = args[0];
            if( args.Length == 2 )
                BuildAgentWorkingDirectory = args[1];

            TeamFoundationServer tfs = new TeamFoundationServer(tfsServer);
            tfs.EnsureAuthenticated();

            IBuildServer bs = (IBuildServer)tfs.GetService(typeof(IBuildServer));
            ICommonStructureService css = (ICommonStructureService)tfs.GetService(typeof(ICommonStructureService));

            ProjectInfo[] projectList = css.ListAllProjects();
            var controller = bs.QueryBuildControllers(true).First();

            foreach (var project in projectList)
            {
                string projectName = project.Name;
                if (bs.QueryBuildDefinitions(projectName).Count() != 0)
                {
                    var agents = controller.Agents.Where(a => a.Name == projectName);

                    if (agents.Count() == 0)
                    {
                        IBuildAgent agent = AddBuildAgent(controller, projectName);
                        agents = new List<IBuildAgent> { agent };
                    }
                    foreach (IBuildAgent a in agents)
                    {
                        if (!AgentHasTag(projectName, a))
                        {
                            AddTagToBuildAgent(projectName, a);
                        }
                    }

                    foreach (IBuildDefinition build in bs.QueryBuildDefinitions(projectName))
                    {
                        AddTagToBuildDefinition(projectName, build);
                    }
                }
            }
        }

        private static bool AgentHasTag(string projectName, IBuildAgent a)
        {
            return a.Tags.Where(t => t == projectName).Count() != 0;
        }

        private static IBuildAgent AddBuildAgent(IBuildController controller, string projectName)
        {
            IBuildAgent agent = controller.ServiceHost.CreateBuildAgent(projectName, BuildAgentWorkingDirectory);
            controller.AddBuildAgent(agent);
            agent.Save();
            return agent;
        }

        private static void AddTagToBuildDefinition(string tag, IBuildDefinition build)
        {
            const string AgentSettingsElement = "{clr-namespace:Microsoft.TeamFoundation.Build.Workflow.Activities;assembly=Microsoft.TeamFoundation.Build.Workflow}AgentSettings";

            XDocument doc = XDocument.Parse(build.ProcessParameters);
            var agentSettings = doc.Root.Descendants(AgentSettingsElement);
            if (agentSettings.Count() == 0)
            {
                doc.Root.Add(
                    new XElement(AgentSettingsElement,
                        new XAttribute("{http://schemas.microsoft.com/winfx/2006/xaml}Key", "AgentSettings"),
                        new XAttribute("Tags", tag)));
            }
            else
            {
                var tags = agentSettings.First().Attributes("Tags");
                tags.First().Value = tag;
            }
            build.ProcessParameters = doc.ToString();
            build.Save();
        }

        private static void AddTagToBuildAgent(string tag, IBuildAgent a)
        {
            a.Tags.Add(tag);
            a.Save();
        }
    }
}
```

---

## Comments

*Imported from the original WordPress site. Closed for new replies.*

> **Patrick Carnahan** — 20 Jan 2010
>
> Originally posted on: <http://geekswithblogs.net/jakob/archive/2009/12/08/tfs-2010-ndash-managing-build-agents-using-the-api.aspx#502561>
>
> Just wanted to follow up on your non-code content. You mentioned that you were using tags to essentially make all builds that deploy a database use the same agent, effectively serializing their execution. There is another way to accomplish this .. we provided an activity called SharedResourceScope that may be used to lock any resource which is identified by a user-defined string. This allows a secondary locking mechanism for global resources, such as publishing to the symbol store (if you take a look at the default template you will actually find where we use this to synchronize invocations of the PublishSymbols activity on a per-share basis.

> **Arshad** — 11 May 2010
>
> Originally posted on: <http://geekswithblogs.net/jakob/archive/2009/12/08/tfs-2010-ndash-managing-build-agents-using-the-api.aspx#518955>
>
> I have a question. \
> \
> Suppose I have some build definition called "Continuous.Script.Deploy". The purpose of this build is to deploy latest scripts on all build agents, so that all other builds which need these scripts will always use the latest.\
> \
> I was able to do it with TFS 2008 API as I can create a build request and queue the build on all available agent for that project. But in TFS 2010 there is "build controller" in between to which we can request to queue build. And build controller will queue it only once on a free build agent in its pool.\
> \
> So, is there any way we can queue a particular build on all pooled build agent agents using TFS 2010 API?\
> \
> Thank you in anticipation.

> **Jakob Ehn** — 11 May 2010
>
> Originally posted on: <http://geekswithblogs.net/jakob/archive/2009/12/08/tfs-2010-ndash-managing-build-agents-using-the-api.aspx#518990>
>
> Arshad:\
> \
> When queuing a build, you can use the Name filter in the Agent settings to specify what agent to execute the build on. Set this filter when queueing the build using the API and you should be fine\
> \
> /Jakob

> **Arshad** — 13 May 2010
>
> Originally posted on: <http://geekswithblogs.net/jakob/archive/2009/12/08/tfs-2010-ndash-managing-build-agents-using-the-api.aspx#519474>
>
> Jakob:\
> \
> Thank you. Your suggestion worked for me. And also helped me to explore TFS API more..!!

> **tim** — 04 Nov 2010
>
> Originally posted on: <http://geekswithblogs.net/jakob/archive/2009/12/08/tfs-2010-ndash-managing-build-agents-using-the-api.aspx#546014>
>
> I'm trying to do something similar - but using the TFS Build Workflow Template.\
> \
> I have 2 build agents: 1 for building Manual builds and 1 for scheduled and CI builds.\
> \
> In the default template there is an AgentSettings argument. I'm adding BuildDetail.Reason.ToString() to the AgentSettings.Tags collection so that the correctly tagged build agent can run the build, however this doesn't seem to be working. The build agents seem to be just ignoring the tags. Any idea whats going on?

---
title: "How To: Automatically Enable Checkin Policies for new TFS Team Projects"
date: 2009-03-20T14:12:46Z
slug: how-to-automatically-enable-checkin-policies-for-new-tfs-team-projects
categories: [TFS]
aliases: [/2009/03/how-to-automatically-enable-checkin-policies-for-new-tfs-team-projects/]
---

When creating new team projects in TFS, the project is created from a project template, that basically is a set of XML files. Here you can define all your work item types, queries, reports, portal site and some other things. One of the things that you **can’t** specify here, is what checkin policies that you want to enable for that team project. At our company, we usually create a new team project for every customer so for every new customer we need to manually modify the checkin policies for that project to match our company policy.

That is tedious and easy to forget, so it must of course be automated! :-)  Since TFS generates a **ProjectCreatedEvent** every time a team project is created, that seems like a good place to start. In addition we must find a way to enable a checkin policy on a given team project. After quite some searching around, I found a [blog post](http://blogs.msdn.com/buckh/archive/2007/03/01/how-to-enable-a-checkin-policy-via-the-version-control-api.aspx) by Buck Hodges that shows the API for reading and updating checkin policies for a team project.

The source code for the web service is shownbelow. To add a subscription for the **ProjectedCreatedEvent** and map it to the web service, use the following command line statement (bissubscribe is installed on the Team Foundation Server app tier): \
**"C:Program FilesMicrosoft Visual Studio 2008 Team Foundation ServerTF SetupBisSubscribe.exe" /eventType ProjectCreatedEvent /address** [**http://SERVER/NewTeamProjectEventService/NewTeamProjectEventService.asmx**](http://SERVER/NewTeamProjectEventService/NewTeamProjectEventService.asmx) **/deliveryType Soap /domain** [**http://TFSSERVER:8080**](http://TFSSERVER:8080)

Note that the web service reads the assembly and the checkin policies (separated by ;) from the app settings. As of now, this only makes it possible to read checkin policies from one assembly, but it should'n’t be that hard to extend the code to allow for mutiple assemblies. I will post an update when I have implemented this functionality.

Also note that the checkin policies must be installed on the server running the web service. I have not found another way to get a hold of the [PolicyType](http://msdn.microsoft.com/en-us/library/microsoft.teamfoundation.versioncontrol.client.policytype(VS.80).aspx) references than to use the **Workstation.Current.InstalledPolicyTypes** property.

```csharp
[WebService(Namespace = "http://tempuri.org/")]
[WebServiceBinding(ConformsTo = WsiProfiles.BasicProfile1_1)]
public class NewTeamProjectEventService
{
    [SoapDocumentMethod(Action = http://schemas.microsoft.com/TeamFoundation/2005/06/Services/Notification/03/Notify,
                        RequestNamespace = "http://schemas.microsoft.com/TeamFoundation/2005/06/Services/Notification/03")]
    [WebMethod(MessageName = "Notify")]
    public EventResult Notify(string eventXml)
    {
        try
        {
            XmlDocument objXML = new XmlDocument();
            objXML.LoadXml(eventXml);

            string projectName = (objXML.GetElementsByTagName("Name")[0] as XmlElement).InnerText;
            if (objXML.DocumentElement.Name == "ProjectCreatedEvent")
            {
                string strTFSServer = Properties.Settings.Default.TFSServer;
                TeamFoundationServer tfs = new TeamFoundationServer(strTFSServer, new NetworkCredential(Properties.Settings.Default.TFSLogin,
                                                                                                        Properties.Settings.Default.TFSPassword,
                                                                                                        Properties.Settings.Default.TFSDoman));
                tfs.Authenticate();
                VersionControlServer service = (VersionControlServer)tfs.GetService(typeof(VersionControlServer));
                TeamProject teamProject = service.GetTeamProject(projectName);

                List<PolicyEnvelope> policies = new List<PolicyEnvelope>();
                string assembly = Properties.Settings.Default.CheckinPolicyAssembly;

                foreach (string type in Properties.Settings.Default.CheckinPoliciesToApply.Split(';'))
                {
                    Assembly checkinPolicyAssembly = Assembly.LoadFile(assembly);
                    object o = checkinPolicyAssembly.CreateInstance(type);

                    if (o is IPolicyDefinition)
                    {
                        IPolicyDefinition def = o as IPolicyDefinition;

                        PolicyEnvelope[] checkinPolicies = new PolicyEnvelope[1];
                        bool foundPolicy = false;
                        foreach (PolicyType policyType in Workstation.Current.InstalledPolicyTypes)
                        {
                            if (policyType.Name == def.Type)
                            {
                                policies.Add(new PolicyEnvelope(def, policyType));
                                foundPolicy = true;
                            }
                        }
                        if (!foundPolicy)
                        {
                            throw new ApplicationException(String.Format("The policy {0} is not registered on this machine", def.Type));
                        }
                    }
                    else
                    {
                        throw new ApplicationException(String.Format("Type {0} in assembly {1} does not implement the IPolicyDefinition interface", type, assembly));
                    }
                }
                if (policies.Count > 0)
                {
                    teamProject.SetCheckinPolicies(policies.ToArray());
                }
            }
        }
        catch (Exception e)
        {
            EventLog.WriteEntry("NewTeamProjectEventService", e.Message + "n" + e.StackTrace);
            return new EventResult(false);
        }
        return new EventResult(true);
    }
}
```

Now, there are other things that we also need to do manually for all new team projects. For example we must manually add the build service account to the Build Services group for the new team project. You can’t do this via the process template. So I might extend the project to allow for more things to be applied. Could be a candidate for trying out the [MEF](http://www.codeplex.com/MEF) framework, so it can be a pluggable architecture.

---

## Comments

*Imported from the original WordPress site. Closed for new replies.*

> **Dennes** — 07 Jan 2011
>
> Originally posted on: <http://geekswithblogs.net/jakob/archive/2009/03/20/how-to-automatically-enable-checkin-policies-for-new-tfs-team.aspx#556469>
>
> Hi,\
> \
> Where can I find Microsoft.TeamFoundation.Server.dll so I can use the class EventResult ?\
> \
> Thank you !\
> \

> **Jakob Ehn** — 07 Jan 2011
>
> Originally posted on: <http://geekswithblogs.net/jakob/archive/2009/03/20/how-to-automatically-enable-checkin-policies-for-new-tfs-team.aspx#556580>
>
> @Dennes: The EventResult class i located in the Microsoft.TeamFoundation class which you can find in C:Program Files (x86)Microsoft Visual Studio XXCommon7IDEReferenceAssembliesv2.0

> **Simon Stone** — 17 Jan 2011
>
> Originally posted on: <http://geekswithblogs.net/jakob/archive/2009/03/20/how-to-automatically-enable-checkin-policies-for-new-tfs-team.aspx#558366>
>
> I just ran into this article. What I cannot figure out it is how to create a policy that requires input such as the Custom Path Policy. Any ideas?\
> \
> Thanks\

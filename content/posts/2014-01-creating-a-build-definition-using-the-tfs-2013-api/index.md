---
title: Creating a Build Definition using the TFS 2013 API
date: 2014-01-15T21:55:13Z
slug: creating-a-build-definition-using-the-tfs-2013-api
categories: [TFS, TFS API, TFS Build, Visual Studio 2013]
aliases: [/2014/01/creating-a-build-definition-using-the-tfs-2013-api/]
---

Almost four years ago I [wrote a post](http://geekswithblogs.net/jakob/archive/2010/04/26/creating-a-build-definition-using-the-tfs-2010-api.aspx) on how to create a build definition programmatically using the TFS 2010 API. The code is partyl still valid, but since a lot of the information in a build definition is dependent on the build process template, the code in the blog \
does not work properly for the TFS 2013 default build templates. In addition, since the introduction of Git in TFS 2013, there are some other differences in how you create a build definition for a Git team project compared to a TFVC team project.

So, in this post I will show an updated version of the code for creating a build defintion. I will actually show two samples, one for the GitTemplate.12.xaml and one for the TfvcTemplate.xaml which are the default template used in TFS 2013.

### Creating a Git Build definition (GitTemplate.12.xaml)

```
Here is the code for creating a build definition using the GitTemplate.12.xaml build process template
```

```
//Create build definition and give it a name and desription
IBuildDefinition buildDef = buildServer.CreateBuildDefinition(tp);
buildDef.Name = "ATestBuild";
buildDef.Description = "A description for this build defintion";
buildDef.ContinuousIntegrationType = ContinuousIntegrationType.Individual; //CI

//Controller and default build process template
buildDef.BuildController = buildServer.GetBuildController("Hosted Build Controller");
var defaultTemplate = buildServer.QueryProcessTemplates(tp).First(p => p.TemplateType == ProcessTemplateType.Default);
buildDef.Process = defaultTemplate;

//Drop location
buildDef.DefaultDropLocation = "#/";    //set to server drop

//Source Settings
var provider = buildDef.CreateInitialSourceProvider("TFGIT");
provider.Fields["RepositoryName"] = "Git";
provider.Fields["DefaultBranch"] = "refs/heads/master";
provider.Fields["CIBranches"] = "refs/heads/master";
provider.Fields["RepositoryUrl"] = url + "/_git/Git";
buildDef.SetSourceProvider(provider);

//Process params
var process = WorkflowHelpers.DeserializeProcessParameters(buildDef.ProcessParameters);

//What to build
process.Add("ProjectsToBuild", new[]{"Test.sln"});
process.Add("ConfigurationsToBuild", new[]{"Mixed Platforms|Debug"});

//Advanced build settings
var buildParams = new Dictionary<string, string>();
buildParams.Add("PreActionScriptPath", "/prebuild.ps1");
buildParams.Add("PostActionScriptPath", "/postbuild.ps1");
var param = new BuildParameter(buildParams);
process.Add("AdvancedBuildSettings", param);

//test settings
var testParams = new Dictionary<string, object>
                                 {
                                     { "AssemblyFileSpec", "*.exe" },
                                     { "HasRunSettingsFile", true },
                                     { "ExecutionPlatform", "X86" },
                                     { "FailBuildOnFailure", true },
                                     { "RunName", "MyTestRunName" },
                                     { "HasTestCaseFilter", false },
                                     { "TestCaseFilter", null }
                                 };

var runSettingsForTestRun = new Dictionary<string, object>
                                            {
                                                { "HasRunSettingsFile", true },
                                                { "ServerRunSettingsFile", "" },
                                                { "TypeRunSettings", "CodeCoverageEnabled" }
                                            };
testParams.Add("RunSettingsForTestRun", runSettingsForTestRun);

process.Add("AutomatedTests", new[]{ new BuildParameter(testParams)});

//Symbol settings
process.Add("SymbolStorePath", @"\serversymbolssomepath");

buildDef.ProcessParameters = WorkflowHelpers.SerializeProcessParameters(process);

//Retention policy
buildDef.RetentionPolicyList.Clear();
buildDef.AddRetentionPolicy(BuildReason.Triggered, BuildStatus.Succeeded, 10, DeleteOptions.All);
buildDef.AddRetentionPolicy(BuildReason.Triggered, BuildStatus.Failed, 10, DeleteOptions.All);
buildDef.AddRetentionPolicy(BuildReason.Triggered, BuildStatus.Stopped, 1, DeleteOptions.All);
buildDef.AddRetentionPolicy(BuildReason.Triggered, BuildStatus.PartiallySucceeded, 10, DeleteOptions.All);

//Lets save it
buildDef.Save();
```

**Some things to note here:**

- The [IBuildDefinitionSourceProvider](http://msdn.microsoft.com/en-us/library/microsoft.teamfoundation.build.client.ibuilddefinitionsourceprovider.aspx) interface is new in TFS 2013, and the reason for it is of course to abstract the differences between TFVC and Git source control. As you can see, we use the “TFGIT”
  to select the correct provider, and then we use the Fields property to populate it with information
- The process parameters are created by using dictionaires, with the corresponding key and values. If you are familiar with the GitTemplate.12.xaml, you will recognize the name of these parameters.
- As for drop locations, in TFS 2013 you can select between no drop location, a drop folder (share) or a server drop, which means the output is stored inside TFS and accessible from the web access.
  In the sample above, we specify #/ which (not that obvious) means a server drop. If you want to use a share drop location, just specify the server path for the DefaultDropLocation

### Creating a TFVC Build definition (TfvcTemplate.12.xaml)

AS it turns out, creating a TFVC build definition using the TfvcTemplate.12.xaml is almost identical, since the build team went to great effort and abstracted away most differences. The only difference in fact, at least when it comes to the most common settings is how you define the workspace mappings. And this code is the same as it was in TFS 2010/2012. In addition, you don’t need to create a source provider, because there is nothing that needs to be configured other than the workspace.

Here is the full sample for TFVC:

```
//Create build definition and give it a name and desription
IBuildDefinition buildDef = buildServer.CreateBuildDefinition(tp);
buildDef.Name = "ATestBuild";
buildDef.Description = "A description for this build defintion";
buildDef.ContinuousIntegrationType = ContinuousIntegrationType.Individual; //CI

//Controller and default build process template
buildDef.BuildController = buildServer.GetBuildController("Hosted Build Controller");
var defaultTemplate = buildServer.QueryProcessTemplates(tp).First(p => p.TemplateType == ProcessTemplateType.Default);
buildDef.Process = defaultTemplate;

//Drop location
buildDef.DefaultDropLocation = "#/";    //set to server drop

//Source Settings
buildDef.Workspace.AddMapping("$/Path/project.sln", "$(SourceDir)", WorkspaceMappingType.Map);
buildDef.Workspace.AddMapping("$/OtherPath/", "", WorkspaceMappingType.Cloak);

//Process params
var process = WorkflowHelpers.DeserializeProcessParameters(buildDef.ProcessParameters);

//What to build
process.Add("ProjectsToBuild", new[]{"Test.sln"});
process.Add("ConfigurationsToBuild", new[]{"Mixed Platforms|Debug"});

//Advanced build settings
var buildParams = new Dictionary<string, string>();
buildParams.Add("PreActionScriptPath", "/prebuild.ps1");
buildParams.Add("PostActionScriptPath", "/postbuild.ps1");
var param = new BuildParameter(buildParams);
process.Add("AdvancedBuildSettings", param);

//test settings
var testParams = new Dictionary<string, object>
                                 {
                                     { "AssemblyFileSpec", "*.exe" },
                                     { "HasRunSettingsFile", true },
                                     { "ExecutionPlatform", "X86" },
                                     { "FailBuildOnFailure", true },
                                     { "RunName", "MyTestRunName" },
                                     { "HasTestCaseFilter", false },
                                     { "TestCaseFilter", null }
                                 };

var runSettingsForTestRun = new Dictionary<string, object>
                                            {
                                                { "HasRunSettingsFile", true },
                                                { "ServerRunSettingsFile", "" },
                                                { "TypeRunSettings", "CodeCoverageEnabled" }
                                            };
testParams.Add("RunSettingsForTestRun", runSettingsForTestRun);

process.Add("AutomatedTests", new[]{ new BuildParameter(testParams)});

//Symbol settings
process.Add("SymbolStorePath", @"\serversymbolssomepath");

buildDef.ProcessParameters = WorkflowHelpers.SerializeProcessParameters(process);

//Retention policy
buildDef.RetentionPolicyList.Clear();
buildDef.AddRetentionPolicy(BuildReason.Triggered, BuildStatus.Succeeded, 10, DeleteOptions.All);
buildDef.AddRetentionPolicy(BuildReason.Triggered, BuildStatus.Failed, 10, DeleteOptions.All);
buildDef.AddRetentionPolicy(BuildReason.Triggered, BuildStatus.Stopped, 1, DeleteOptions.All);
buildDef.AddRetentionPolicy(BuildReason.Triggered, BuildStatus.PartiallySucceeded, 10, DeleteOptions.All);

//Lets save it
buildDef.Save();
```

Hope you find this useful!

---

## Comments

*Imported from the original WordPress site. Closed for new replies.*

> **Sarkis** — 28 Mar 2014
>
> Originally posted on: <http://geekswithblogs.net/jakob/archive/2014/01/15/creating-a-build-definition-using-the-tfs-2013-api.aspx#636720>
>
> Thanks for the valuable post. Which library is referenced for BuildParameter type?

> **Sarkis** — 28 Mar 2014
>
> Originally posted on: <http://geekswithblogs.net/jakob/archive/2014/01/15/creating-a-build-definition-using-the-tfs-2013-api.aspx#636721>
>
> I am trying to edit the existing BuildParameters using the API. Could you point me to the right direction?\
> \
> I am able to read them using the deserializeprocessparameters as you suggested but not able to edit them.\
> \
> Thanks,\
> Sarkis\
> \

> **Sarkis** — 28 Mar 2014
>
> Originally posted on: <http://geekswithblogs.net/jakob/archive/2014/01/15/creating-a-build-definition-using-the-tfs-2013-api.aspx#636722>
>
> Found the way to set parameters. Here it is:\
> \
>  process["ParamName"] = "ParamValue";\
> \
> buildDefinition.ProcessParameters = WorkflowHelpers.SerializeProcessParameters(process);

> **Sarkis** — 28 Mar 2014
>
> Originally posted on: <http://geekswithblogs.net/jakob/archive/2014/01/15/creating-a-build-definition-using-the-tfs-2013-api.aspx#636741>
>
> One more issue I am having. Somehow DefaultDropLocation is not being saved using the following:\
> \
> buildDefinition.DefaultDropLocation = "\test";\
> \
> Is this an MS Bug?\
> \

> **Zech** — 26 Sep 2014
>
> Originally posted on: <http://geekswithblogs.net/jakob/archive/2014/01/15/creating-a-build-definition-using-the-tfs-2013-api.aspx#640883>
>
> Thanks for sharing this. its very useful.\
> \
> @Sarkis\
> \
> library for BuildParameter Microsoft.TeamFoundation.Build.Common

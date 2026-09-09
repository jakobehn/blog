---
title: Copy TFS Build Definitions between Projects and Collections
date: 2014-06-05T14:50:54Z
slug: copy-tfs-build-definitions-between-projects-and-collections
categories: [TFS, TFS API, TFS Build, Visual Studio 2013]
aliases: [/2014/06/copy-tfs-build-definitions-between-projects-and-collections/]
---

The last couple of years it has become apparent that using multiple team projects in TFS is generally a bad idea. There are of course exceptions to this, but there are a lot ot things that becomes much easier to do when you put all of your projects and team in the same team project.

Fellow ALM MVP Martin Hinshelwood has blogged about [this several times](http://nakedalm.com/one-team-project/), as well as other [people](http://geekswithblogs.net/Optikal/archive/2013/09/05/153944.aspx) in the community. In particular, using the backlog and portfolio management tools makes much more sense when everything is located in the same team project.

Consolidating multiple team projects into one is not that easy unfortunately, it involves migrating source code, work items, reports etc.  Another thing that also need to be migrated is build definitions. It is possible to clone build definitions within the same team project using the TFS power tools.

The [Community TFS Build Manager](http://visualstudiogallery.msdn.microsoft.com/73bf2d8e-aec6-406c-8e7f-1c678e46557f) also lets you clone build definitions to other team projects. But there is no tool that allows you to clone/copy a build definition to another collection. So, I whipped up a simple console application that let you do this.

The tool can be downloaded from

[https://onedrive.live.com/redir?resid=EE034C9F620CD58D!8162&authkey=!ACTr56v1QVowzuE&ithint=file%2c.zip](https://onedrive.live.com/redir?resid=EE034C9F620CD58D!8162&authkey=!ACTr56v1QVowzuE&ithint=file%2c.zip "https://onedrive.live.com/redir?resid=EE034C9F620CD58D!8162&authkey=!ACTr56v1QVowzuE&ithint=file%2c.zip")

##

## Using CopyTFSBuildDefinitions

You use the tool like this:

*CopyTFSBuildDefinitions  SourceCollectionUrl  SourceTeamProject  BuildDefinitionName  DestinationCollectionUrl  DestinationTeamProject [NewDefinitionName]*

**Arguments**

- **SourceCollectionUrl** \
  The URL to the TFS collection that contains the team project with the build definition that you want to copy \
- **SourceTeamProject** \
  The name of the team project that contains the build definition \
- **BuildDefinitionName** \
  Name of the build definition \
- **DestinationCollectionUrl** \
  The URL to the TFS collection that contains the team project that you want to copy your build definition to \
- **DestinationTeamProject** \
  The name of the team project in the destination collection \
- **NewDefinitionName (Optional)** \
  Use this to override the name of the new build definition. If you don’t specify this, the name will the same as the original one

Example:

*\
CopyTFSBuildDefinitions  <https://jakob.visualstudio.com> DemoProject  WebApplication.CI <https://anotheraccount.visualstudio.com>*

### Notes

- Since we are (potentially) create a build definition in a new collection, there is no guarantee that the various paths that are defined in the build definition exist in the new collection. For example, a build definition refers to server paths in TFVC or repos + branches in TFGit. It also refers to build controllers that definitely don’t exist in the new collection. So there will be some cleanup to do after you copy your build definitions. You can fix some of these using the Community TFS Build Manager, for example it is very easy to apply the correct build controller to a set of build definitions

- The problem stated above also applies to build process templates. However, the tool tries to find a build process template in the new team project with the same file name as the one that existed in the old team project. If it finds one, it will be used for the new build definition. Otherwise is will use the default build template

- If you want to run the tool for many build definitions, you can use this SQL scripts, compliments of Mr. Scrum/ALM MVP [Richard Hundhausen](http://blog.accentient.com/author/richard/) to generate the necessary commands: \

  USE Tfs_Collection

  GO

  SELECT 'CopyTFSBuildDefinitions.exe <http://SERVER:8080/tfs/collection> "' + P.ProjectName + '" "' + REPLACE(BD.DefinitionName,'','') + '" <http://NEWSERVER:8080/tfs/COLLECTION> TEAMPROJECT'

    FROM tbl_Project P

         INNER JOIN tbl_BuildGroup BG on BG.TeamProject = P.ProjectUri

         INNER JOIN tbl_BuildDefinition BD on BD.GroupId = BG.GroupId

    ORDER BY P.ProjectName, BD.DefinitionName

Hope that helps, let me know if you have any problems with the tool or if you find it useful

---

## Comments

*Imported from the original WordPress site. Closed for new replies.*

> **MrHinsh** — 06 Jun 2014
>
> Originally posted on: <http://geekswithblogs.net/jakob/archive/2014/06/05/copy-tfs-build-definitions-between-projects-and-collections.aspx#638219>
>
> When are you going to integrate this into the TFS Integration Tools as a new adapter type. Could be really useful in there 😊

> **Jakob Ehn** — 06 Jun 2014
>
> Originally posted on: <http://geekswithblogs.net/jakob/archive/2014/06/05/copy-tfs-build-definitions-between-projects-and-collections.aspx#638220>
>
> When the integration tools is open source Martin :-)

> **Mia** — 28 Jun 2014
>
> Originally posted on: <http://geekswithblogs.net/jakob/archive/2014/06/05/copy-tfs-build-definitions-between-projects-and-collections.aspx#638579>
>
> Hello Jakob, \
> \
> there is actually a tool which does this. It is commerical, but you can use it 30 days for free.\
> \
> http://visualstudiogallery.msdn.microsoft.com/ec36f618-d122-48a3-8236-7d9cd19791ee\
> \
> Mia\

> **iladan** — 08 Aug 2014
>
> Originally posted on: <http://geekswithblogs.net/jakob/archive/2014/06/05/copy-tfs-build-definitions-between-projects-and-collections.aspx#639390>
>
> As i know, TFS integration tool is a free tool and have certain issues.\
> What are other alternatives if any?

> **Jakob Ehn** — 18 Nov 2014
>
> Originally posted on: <http://geekswithblogs.net/jakob/archive/2014/06/05/copy-tfs-build-definitions-between-projects-and-collections.aspx#641461>
>
> @iladan: Opshub has a commercial system that supports work item migration/synchronization

> **Iqstr** — 27 Jul 2015
>
> Originally posted on: <http://geekswithblogs.net/jakob/archive/2014/06/05/copy-tfs-build-definitions-between-projects-and-collections.aspx#645502>
>
> awesome tools. it saved me hours...

> **Ashish** — 13 Nov 2015
>
> Originally posted on: <http://geekswithblogs.net/jakob/archive/2014/06/05/copy-tfs-build-definitions-between-projects-and-collections.aspx#647022>
>
> Is the perfect tool I was looking for. Can you recompile for VS2015 too?

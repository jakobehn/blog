---
title: Avoiding TF237124 when Creating Work Items in New Areas
date: 2012-01-20T09:42:41Z
slug: avoiding-tf237124-when-creating-work-items-in-new-areas
categories: [TFS, TFS API, Visual Studio 2010]
aliases: [/2012/01/avoiding-tf237124-when-creating-work-items-in-new-areas/]
---

At my [company](http://www.inmetacrayon.no/English/about_inmeta/Pages/default.aspx) we write a lot of tools and extensions that uses the TFS API to automate various things for us. A very common thing to automate is the creation of work items and the areas and iterations structure.

Creating a work item using the TFS API is simple, just connect to TFS, get the [WorkItemStore](http://msdn.microsoft.com/en-us/library/microsoft.teamfoundation.workitemtracking.client.workitemstore(v=vs.100).aspx) service object and create a new work item and set any fields that you want to: \
 **\
Creating a work item**

```javascript
Code highlighting produced by Actipro CodeHighlighter (freeware)
http://www.CodeHighlighter.com/

//Connect to TFS and get the WorkItemStore object
var tfs = new TfsTeamProjectCollection(new Uri("http://localhost:8080/tfs"));
var wis = tfs.GetService(typeof(WorkItemStore)) as WorkItemStore;

//Get team project
var teamProject = wis.Projects["Demo"];

//Get the Bug Work Item Type
var wit = teamProject.WorkItemTypes["Bug"];

//Create a new Bug work item and set the title field
WorkItem wi = new WorkItem(wit);
wi.Title = "New Bug In New Area";
wi.Save();
```

Creating an area or iteration is equally simple:

**\
Creating an area**

```javascript
Code highlighting produced by Actipro CodeHighlighter (freeware)
http://www.CodeHighlighter.com/

//Connect to TFS and get the ICommonStructureService object
var tfs = new TfsTeamProjectCollection(new Uri("http://localhost:8080/tfs"));
var css = tfs.GetService(typeof(ICommonStructureService)) as ICommonStructureService;

//Get the root path of the new area
string rootNodePath = "\Demo\Area";
var pathRoot = css.GetNodeFromPath(rootNodePath);

//Create the new area, in this case it will be a new root area
css.CreateNode("NewRootArea", pathRoot.Uri);
```

BUT (yes there is a but, you could sense it coming), when you combine these two fellows into one task, e.g. create a new area (or iteration) and then create a new work item in that area, chances are high that you will receive the following exception:

```
Microsoft.TeamFoundation.WorkItemTracking.Client.ValidationException: TF237124: Work Item is not ready to save

   at Microsoft.TeamFoundation.WorkItemTracking.Client.WorkItem.Save(SaveFlags saveFlags)

   at Microsoft.TeamFoundation.WorkItemTracking.Client.WorkItem.Save()
```

The meaning of the error is not obvious, but if you would call the [Validate()](http://msdn.microsoft.com/en-us/library/microsoft.teamfoundation.workitemtracking.client.workitem.validate(v=vs.100).aspx) method before calling Save() (which you should, of course) you would see that it returns the Area field indicating that this field is the problem.

The underlying problem here is that in the TFS Data Store, work items and areas/iterations are persisted in two different stores. And these stores need to be synchronized before you can reference any new items that you added. You’ll notice the same issue in Visual Studio as well, when you create a new area or iteration in Team Explorer, you need to refresh Team Explorer in order to use the new nodes for work items.

But how do we do this programmatically? There actually two things that needs to be done:

1. Request that the work item store is synchronized with the Common Structure store
2. Refresh the local cache

Which is translated into the following code

**\
Synchronize External Stores**

```csharp
Code highlighting produced by Actipro CodeHighlighter (freeware)
http://www.CodeHighlighter.com/

//Synchronize the work item store with external stores (e.g. CSS)
private static void SyncExternalStructures(TfsTeamProjectCollection tfs, WorkItemStore wis,
                                           ICommonStructureService css, string teamProject)
{
    //Get work item server proxy object
    WorkItemServer witProxy = (WorkItemServer)tfs.GetService(typeof(WorkItemServer));
    //Get the team project
    ProjectInfo projInfo = css.GetProjectFromName(teamProject);
    //Sync External Store
    witProxy.SyncExternalStructures(WorkItemServer.NewRequestId(), projInfo.Uri);
    //Refresh local cache
    wis.RefreshCache();
}
```

Call this method after creating the area/iterations and before creating the new work item and it will work as expected

---

## Comments

*Imported from the original WordPress site. Closed for new replies.*

> **Ohad Tsamir** — 19 Jan 2016
>
> You just solved my problem cleanly and accurately, and this resource is quite poorly documented and was extremely hard to find on this world wide web.
>
> Many thanks :)
>
> Ohad Tsamir,\
> Senior software developer @Independer

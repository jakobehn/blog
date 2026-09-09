---
title: Writing a Code Coverage Checkin Policy
date: 2009-02-23T13:58:40Z
slug: writing-a-code-coverage-checkin-policy
categories: [TFS]
aliases: [/2009/02/writing-a-code-coverage-checkin-policy/]
---

**The source code for this policy is available here :** [**http://www.codeplex.com/TFSCCCheckinPolicy**](http://www.codeplex.com/TFSCCCheckinPolicy "http://www.codeplex.com/TFSCCCheckinPolicy") \
Checkin policies is a great tool in TFS for keeping your code base clean and adhering to your companhy standards and policies.  The checkin policies that are included are very useful, but don’t stop there! Implementing your own custom checkin policy is pretty straight-forward and can soon pay off by stopping people from doing silly things (on purpose or not…).

At our company ([Osiris Data](http://www.osiris.no)) we have developed several small checkin policies that both stop people from breaking our standards, but also helping them to do the right thing. We all make mistakes from time to time, and if a tool can help us not doing them, then that’s pretty good… :-)

For example we have a checkin policy that stop people from checking in binaries into TFS. Of course there are occasions when people are allowed to do this (3rd party dll:s, binary references), so then we check that the binaries are placed in folders that are named according to our naming policies, thereby enforcing standards across the team projects.

I recently saw a post in one of the MSDN forums asking for a checkin policy that would check coverage as part of a check-in. That is, if the latest test run either does not have code coverage at all, or the total code coverage percentage is below a certain treshold, the policy would stop the check-in. I couldn’t find any such checkin policy on the net, so I decided that it would be fun to write one.

The following things must be solved:

1) Locating the latest test run and code coverage information \
2) Analyzing the code coverage information

The first part was simple to implement, unfortunately there does not seem to be anything in the VS.NET extensibility API that allows you to locate the test runs or code coverage information, so I basically had to run through the folder structure beneath the current solution to locate the folder with the latest test run. Simple and rather boring, so I won’t mention that code here.

The second part was a bit worse, since the API for running and analysing code coverage is totally undocumented and, frankly, not supported by MS. However, the following blog post by [Joe](http://blogs.msdn.com/ms_joc/articles/495996.aspx) contained the information I needed in order to load and analyse the code coverage information. As always with unsupported stuff, there is no guarantee that the code will work with new versions of VSTS or even service packs. This code has been tested on VSTS 2008 SP1.

The code coverage result is stored in a proprietary binary format, and is located beneath the test run result. the local folder structure looks like this:

```
Solution
    -----  TestResults
                   ---- TestRun1
                              -----  In
                                       ------ data.coverage
                             ------ Out
                                       ------ Binaries from the instrumented assemblies
```

To programmatically access and analyse the code coverage results, we need a reference to the **Microsoft.VisualStudio.Coverage.Analysis** assembly, which is located in the private assemblies folder of VSTS. In this assembly, we use the **CoverageInfoManager** class to load the coverage file. In addition this class contains a method that returns a typed dataset (method is appropriately called BuildDataSet). This method returns an instance of the **CoverageInfo** class from which we can easily read the information.

The code snippet for loading the coverage file calculating the total code coverage in percent looks like this:

```
CoverageInfoManager.ExePath = binariesFolder;
CoverageInfoManager.SymPath = binariesFolder;
```

```
CoverageInfo ci = CoverageInfoManager.CreateInfoFromFile(codeCoverageFile);
CoverageDS data = ci.BuildDataSet(null);
```

```
uint blocksCovered = 0;
uint blocksNotCovered = 0;
foreach (CoverageDS.ModuleRow m in data.Module)
```

```json
{
    blocksCovered += m.BlocksCovered;
    blocksNotCovered += m.BlocksNotCovered;
}
```

```
return GetPercentCoverage(blocksCovered, blocksNotCovered);
```

Note that we must set the **ExePath** and the **SymPath** properties to the folder where the instrumented assemblies is located. If not, the BuildDataSet method will throw a CoverageException.

So all we have to do then is to implement the [PolicyBase.Evaluate](http://msdn.microsoft.com/en-us/library/microsoft.teamfoundation.versioncontrol.client.policybase.evaluate(VS.80).aspx) method and compare the totalCodeCoverage with the configurable treshold. This treshold is configured by implementing the **CanEdit** and the **Edit** methods. See the source code for how this is done, it is all standard checkin policy stuff.

Hopefully this checkin policy will be useful for some people, let me know about any problems and I will try to fix them asap.

---

## Comments

*Imported from the original WordPress site. Closed for new replies.*

> **Ian Ceicys** — 25 Feb 2009
>
> Originally posted on: <http://geekswithblogs.net/jakob/archive/2009/02/23/writing-a-code-coverage-checkin-policy.aspx#433640>
>
> I'd love to see the source for this checkin policy. Can you please try republishing it to codeplex or sending me the code?\
> \
> Thx.

> **VDeevi** — 25 Jul 2011
>
> Originally posted on: <http://geekswithblogs.net/jakob/archive/2009/02/23/writing-a-code-coverage-checkin-policy.aspx#587340>
>
> Hi Ian,\
> \
> Please find the following link for Source code to this blog information...\
> \
> http://tfscccheckinpolicy.codeplex.com/SourceControl/list/changesets#\
> \
> Thx & Rgds,\
> VDeevi

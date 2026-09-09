---
title: Reember to uninstall all Beta 2 stuff before upgrading to VS 2010 RC
date: 2010-02-09T20:52:05Z
slug: reember-to-uninstall-all-beta-2-stuff-before-upgrading-to-vs-2010-rc
categories: [TFS, Visual Studio 2010]
aliases: [/2010/02/reember-to-uninstall-all-beta-2-stuff-before-upgrading-to-vs-2010-rc/]
---

Yesterday I upgraded my dev laptop to VS 2010 RC. To upgrade to VS 2010 RC you need to first uninstall VS 2010 Beta 2 (which doesn’t really make it an upgrade does it? :-)

I also hade an instance of TFS 2010 Beta 2 om my machine so I uninstalled that as well. The installation of VS 2010 went fine, and then I installed Team Explorer 2010 RC. However, when starting VS and switching to the team explorer, I got the following error:

**Could not load type 'Microsoft.TeamFoundation.Client.TeamFoundationServerBase' from assembly 'Microsoft.TeamFoundation.Client, Version=10.0.0.0, Culture=neutral, PublicKeyToken=b03f5f7f11d50a3a'.**

It turns out that I still had one Beta 2 installation left, namely the TFS 2010 Beta 2 Power Tools. After uninstalling this everything works as expected.

 So, the first impression on VS 2010 RC is good, it is definitelyt faster in startup and loading time. Haven’t really measured build time etc. yes. Unfortunately working with the Workflow Designer (for TFS 2010 Builds) is still painfully slow. On my Dell 2.5GHz 4GB RAM laptop it takes almost 40 seconds to load the default build process template!

I hope that the RTM will improve the performance when it comes to the WF designer, otherwise we will have to resort to editing the .XAML files directly which if course isn’t as nice (and no intellisense yet!)

---

## Comments

*Imported from the original WordPress site. Closed for new replies.*

> **Michel Prevost** — 31 Mar 2010
>
> Originally posted on: <http://geekswithblogs.net/jakob/archive/2010/02/09/reember-to-uninstall-all-beta-2-stuff-before-upgrading-to.aspx#513804>
>
> I have the same problem, but I never installed the Beta 2 tools.

> **Hamid** — 09 Apr 2010
>
> Originally posted on: <http://geekswithblogs.net/jakob/archive/2010/02/09/reember-to-uninstall-all-beta-2-stuff-before-upgrading-to.aspx#514656>
>
> Thanks Jakob,\
> That worked a treat. Although, I had uninstalled TFS2010 Beta2 but I still had PowerTools Beta2 installed on my machine. Uninstalled them and this issue is resolved.\

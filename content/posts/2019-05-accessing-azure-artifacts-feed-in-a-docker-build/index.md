---
title: Accessing Azure Artifacts feed in a Docker build
date: 2019-05-27T20:48:39Z
slug: accessing-azure-artifacts-feed-in-a-docker-build
categories: [Azure DevOps, Build Automation, Docker]
aliases: [/2019/05/accessing-azure-artifacts-feed-in-a-docker-build/]
---

I’ve recently given talks at conferences and user groups on the topic of using Docker as a build engine, describing the builds using a Dockerfile. This has several advantages, such as fully consistent build no matter where you run it, no dependencies necessary except Docker.

![Image result for docker](https://www.docker.com/sites/default/files/social/docker_facebook_share.png)

Some things become a bit tricker though, [I’ve blogged previously](/2019/01/running-net-core-unit-tests-with-docker-and-azure-pipelines/) about how to run unit tests in a Docker build, including getting the test results out of the build container afterwards.

Another thing that you will soon hit if you start with Dockerfile builds, is how to restore packages from an authenticated NuGet feed, such as Azure Artifacts. The reason this is problematic is that the build will run inside a docker container, as a Docker user that can’t authenticate to anything by default. If you build a projects that references a package located in an Azure Artifacts feed, you’ll get an error like this:

```
Step 4/15 : RUN dotnet restore -s "https://pkgs.dev.azure.com/jakob/_packaging/DockerBuilds/nuget/v3/index.json" -s "https://api.nuget.org/v3/index.json" "WebApplication1/WebApplication1.csproj"
---> Running in 7071b05e2065
/usr/share/dotnet/sdk/2.2.202/NuGet.targets(119,5): error : Unable to load the service index for source https://pkgs.dev.azure.com/jakob/_packaging/DockerBuilds/nuget/v3/index.json. [/src/WebApplication1/WebApplication1.csproj]
/usr/share/dotnet/sdk/2.2.202/NuGet.targets(119,5): error :   Response status code does not indicate success: 401 (Unauthorized). [/src/WebApplication1/WebApplication1.csproj]
The command '/bin/sh -c dotnet restore -s "https://pkgs.dev.azure.com/jakob/_packaging/DockerBuilds/nuget/v3/index.json" -s "https://api.nuget.org/v3/index.json" "WebApplication1/WebApplication1.csproj"' returned a non-zero code: 1
```

The output log above shows a 401 (Unauthorized) when we run a dotnet restore command.

### Using the Azure Artifacts Credential Provider in a Dockerfile

![Image result for azure artifacts](https://azurecomcdn.azureedge.net/cvt-d60be49385e03ebef7dda9e9a7bea886312b0913b80936120559d89279fa3561/images/page/services/devops/hero-images/artifacts-hero.jpg)

To solve this, Microsoft supplies a credential provider for Azure Artifacts, that you can find here <https://github.com/microsoft/artifacts-credprovider>

NuGet wil look for installed credential providers and, depending on context, either prompt the user for credentials and store it in the credential manager of the current OS, or for CI scenarios we need to pass in the necessary informtion and the credential provider will then automatically do the authentication.

To use the credential provider in a Dockerfile build, you need to download and configure it, and also be sure to specify the feed when you restore your projects. Here is snippet from a Dockerfile that does just this:\
> **NB**: The full source code is available here <https://dev.azure.com/jakob/dockerbuilds/_git/DockerBuilds?path=%2F4.%20NugetRestore&version=GBmaster>

# Install Credential Provider and set env variables to enable Nuget restore with auth

ARG PAT\
RUN wget -qO- https://raw.githubusercontent.com/Microsoft/artifacts-credprovider/master/helpers/installcredprovider.sh | bash\
ENV NUGET_CREDENTIALPROVIDER_SESSIONTOKENCACHE_ENABLED true\
ENV VSS_NUGET_EXTERNAL_FEED_ENDPOINTS "{\"endpointCredentials\": [{\"endpoint\":\"https://pkgs.dev.azure.com/jakob/_packaging/DockerBuilds/nuget/v3/index.json\", \"password\":\"${PAT}\"}]}"

# Restore packages using authenticated feed\
COPY ["WebApplication1/WebApplication1.csproj", "WebApplication1/"]\
RUN dotnet restore -s "https://pkgs.dev.azure.com/jakob/_packaging/DockerBuilds/nuget/v3/index.json" -s "https://api.nuget.org/v3/index.json" "WebApplication1/WebApplication1.csproj"\

The  VSS_NUGET_EXTERNAL_FEED_ENDPOINTS  is an environment variable that should contain the endpoint credentials for any feed that you need to authenticate against, in a JSON Format. The personal access token is sent to the Dockerfile build using an argument called PAT.

To build this, create a Personal Access Token in your Azure DevOps account, with permissions to read your feeds, then run the following command:\
> docker build -f WebApplication1\Dockerfile -t meetup/demo4 . --build-arg PAT=<token>

You should now see the restore complete successfully

---

## Comments

*Imported from the original WordPress site. Closed for new replies.*

> **Gabriel** — 19 Sep 2019
>
> What happens after the token expires? Will my pipeline fail to build?

> > **jakob** — 17 Jan 2020
> >
> > Yes. But instead of sending in an self generated token, you can use the $(System.AccessToken) variable in Azure Pipelines.
> >
> > See this blogpost about how to enable this token and how to use it:\
> > https://toonvanhoutte.wordpress.com/2018/12/04/authenticate-azure-devops-against-its-own-rest-api/
> >
> > /Jakob

> **Ian** — 20 Sep 2019
>
> Really helpful. Saved me some time. Thanks for posting

> > **jakob** — 17 Jan 2020
> >
> > Thanks for reading :-)

> **Tamas** — 28 Nov 2019
>
> Hi!\
> I am getting a 401 for the given link: https://dev.azure.com/jakob/ignitetour/_git/DockerBuilds?path=%2F4.%20NugetRestore&version=GBmaster

> > **jakob** — 17 Jan 2020
> >
> > Sorry, I've fixed the link now

> **[Jasper Siegmund](https://blog.repsaj.nl)** — 23 Dec 2019
>
> The links mentioned bring me to a "401 - Uh-oh, you do not have access."

> **dpetrizze** — 25 Nov 2020
>
> After following this format, rather than getting a 401, I'm getting a 403 error, "The requested operation is not allowed".
>
> I was able to duplicate the 403 error by issuing a dotnet restore locally in WSL2. I then added the --interactive option and was given the prompt to authenticate with a devicelogin code which (I believe) creates a SessionTokenCache on the local system. After following the steps, the 403 went away and I was able to restore successfully in WSL2.
>
> Unfortunately, --interactive in a docker build does not work.
>
> Do you have any experience with 403 and docker builds? Any ideas how to achieve a similar session token cache for docker builds?

> **Ramesh** — 23 Sep 2021
>
> Thanks for above. Is there any reference for how to access/copy maven package from azure artifacts feed in a Docker image using a dockerfile?

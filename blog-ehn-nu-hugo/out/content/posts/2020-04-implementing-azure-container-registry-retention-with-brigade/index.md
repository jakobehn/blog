---
title: Implementing Azure Container Registry Retention with Brigade
date: 2020-04-22T14:46:16Z
slug: implementing-azure-container-registry-retention-with-brigade
categories: [AKS, Docker, Kubernetes, Microsoft Azure]
aliases: [/2020/04/implementing-azure-container-registry-retention-with-brigade/]
---

If you are doing any work related to containers and Azure, you are most likely using [Azure Container Registry](https://azure.microsoft.com/en-us/services/container-registry/) for storing images. The amoun of storage available for these images depends on the pricing tier you are using.\
If you exceed this amount of storage, you will pay an additional fee for every GB of image data that exceeds the limit. See the table below for the current pricing details.

**Azure Container Registry pricing details**

[![image_thumb[7]](image_thumb7_thumb.png "image_thumb[7]")](image_thumb7.png)

100GB of included storage might sound much, but you will pretty soon find out that your CI pipelines will fill up this space with new image versions being pushed on every commit.

Now, if you select the Premium tier, there is a retention policy feature available (<https://docs.microsoft.com/en-us/azure/container-registry/container-registry-retention-policy>), but the Premium tier will cost you three times as much.

Implementing purging of older images in ACR yourself is easy using the Azure CLI/Powershell, but you need some mechanism of hosting and running these scripts whenever you push a new image to your registry.

This is a perfect case for [Brigade](https://brigade.sh/), it already comes with a Container Registry gateway that will respond to webhooks and translate that into Brigade events, and you can host everything inside your existing Kubernetes cluster.

See my introductory post on Brigade here:\
[https://blog.ehn.nu/2020/01/event-driven-scripting-in-kubernetes-with-brigade/](/2020/01/event-driven-scripting-in-kubernetes-with-brigade/)

The overall solution will look like this:

[![image_thumb[13]](image_thumb13_thumb.png "image_thumb[13]")](image_thumb13.png)

Whenever a new image is pushed the an Azure Container Registry, it will send a request to a Brigade Container Registry gateway running in your Kubernetes cluster of choice. This will in turn kick off a build from a Brigade project, that contains a script that will authenticate back to the registry and purge a selected set of older images.

The source code for the Brigade javascript pipeline, including the custom Bash script is available here:\
<https://github.com/jakobehn/brigade-acr-retention>

Let’s go through the steps needed to get this solution up and running. If you want to, you can use the GitHub repository directly, or you’ll want to store these scripts in your own source control.

## Create a Service Principal

To be able to purge images in Azure Container Registry from a Docker container running in our Brigade pipeline, we will create a service principal. This can be done by running the following command:

```bash
az ad sp create-for-rbac --name ACRRetentionPolicy
Changing "ACRRetentionPolicy2" to a valid URI of http://ACRRetentionPolicy, which is the required format used for service principal names
{
   "appId": "48408316-6d71-4d36-b4ea-37c63e3e063d",
   "displayName": "ACRRetentionPolicy",
   "name": http://ACRRetentionPolicy,
   "password": "<<EXTRACTED>>",
   "tenant": "<<EXTRACTED>>"
}
```

Make a note of the appId, password and tenantId as you will be using them later on.

## Install Brigade

If you haven’t already, install Brigade in your Kubernetes cluster. Make sure to enable Brigade’s Container Registry gateway by setting the **cr.enabled** property to true:

```bash
helm repo add brigade https://brigadecore.github.io/charts
helm repo update
helm install -n brigade brigade/brigade --set cr.enabled=true,cr.service.type=LoadBalancer
```

Verify that all components of Brigade are running:

PS C:\brigade> kubectl get pods   

**NAME                                            READY   STATUS    RESTARTS   AGE**\
brigade-server-brigade-api-58d879df79-dczl6     1/1     Running   0          8d\
brigade-server-brigade-cr-gw-577f5c787b-kx2m4   1/1     Running   0          8d\
brigade-server-brigade-ctrl-8658f456c4-pbkx2    1/1     Running   0          8d\
brigade-server-kashti-7546c5567b-ltxqm          1/1     Running   0          8d

List the services and make a note of the public IP address of the Container Registry gateway service:

PS C:\brigade> kubectl get svc                                                                                                        \
 **NAME                           TYPE           CLUSTER-IP     EXTERNAL-IP     PORT(S)        AGE**\
brigade-server-brigade-api     ClusterIP      10.0.188.158   <none>          7745/TCP       8d\
brigade-server-brigade-cr-gw   LoadBalancer   10.0.6.148     40.114.186.81   80:31844/TCP   8d\
brigade-server-kashti          ClusterIP      10.0.193.112   <none>          80/TCP         8d\
kubernetes                     ClusterIP      10.0.0.1       <none>          443/TCP        13d

## Brigade script

Every Brigade pipeline reference a Javascript file that will respond to various events and chain the jobs together using container images. As seen below, the necessary parameters are passed in as environment variables.\
The values of the variables are fetched from the secrets from the Brigade project that we’ll create in the next step.

When the image_push event is received (from the Brigade Container Registry gateway), the script creates a job, passes in the environment variables and define the tasks to be run inside the container. We are using the **mcr.microsoft.com/azure-cli** Docker image, which is the official image for using the Azure CLI inside a container. The task runs the **purge-images.sh** script, which is available in the /src folder. When a Brigade project refers to a Git repository, the source will automatically be cloned into this folder inside the container, using a Git side-car container.

const { events, Job} = require("brigadier");

```
events.on("image_push", async (e, p) => {

     var purgeStep = new Job("purge", "mcr.microsoft.com/azure-cli")
     purgeStep.env = {
         subscriptionName: p.secrets.subscriptionName,
         registryName: p.secrets.registryName,
         repositoryName: p.secrets.repositoryName,
         minImagesToKeep: p.secrets.minImagesToKeep,
         spUserName: p.secrets.spUserName,
         spPassword: p.secrets.spPassword,
         spTenantId: p.secrets.spTenantId
     }
     purgeStep.tasks = [
         "cd src",
         "bash purge-images.sh",
       ];
     purgeStep.run();
```

  });

## Script for purging images from Azure Container Registry

The logic of purging older images from the container registry is implemented in a bash script, called **purge-images.sh**, also located in the GitHub repository. It authenticates using the service principal, and then lists all image tags from the corresponding container registry and deletes all image except the latest X ones (configured through the **minImagesToKeep** environment variable).

```bash
#Login using supplied SP and select the subscription
az login --service-principal --username $spUserName --password $spPassword --tenant $spTenantId
az account set --subscription "$subscriptionName"
```

```bash
# Get all the tags from the supplied repository
TAGS=($(az acr repository show-tags --name $registryName --repository $repositoryName  --output tsv --orderby time_desc))
total=${#TAGS[*]}
```

```bash
for (( i=$minImagesToKeep; i<=$(( $total -1 )); i++ ))
do
      imageName="$repositoryName:${TAGS[$i]}"
      echo "Deleting image: $imageName"
      az acr repository delete --name $registryName --image $imageName --yes
done
```

echo "Retention done"

##

## Creating the Brigade project

To create a project in Brigade, you need the [Brigade CLI](https://docs.brigade.sh/topics/brig/). Running **brig project create** will take you through a wizard where you can fill out the details.\
In this case, I will point it to the GitHub repository that contains the Brigade.js file and the bash script.

Here is the output:

PS C:\acr-retention-policy> brig project create                                                                                       \
? VCS or no-VCS project? VCS\
? Project Name jakobehn/brigade-acr-retention\
? Full repository name github.com/jakobehn/brigade-acr-retention\
? Clone URL (<https://github.com/your/repo.git)> <https://github.com/jakobehn/brigade-acr-retention.git>\
 ? Add secrets? Yes\
?       Secret 1 subscriptionName\
?       Value Microsoft Azure Sponsorship\
? ===> Add another? Yes\
?       Secret 2 registryName\
?       Value jakob\
? ===> Add another? Yes\
?       Secret 3 repositoryName\
?       Value acrdemo\
? ===> Add another? Yes\
?       Secret 4 minImagesToKeep\
?       Value 5\
? ===> Add another? Yes\
?       Secret 5 spUserName\
?       Value <<EXTRACTED>>\
? ===> Add another? Yes\
?       Secret 6 spPassword\
?       Value <<EXTRACTED>>\
? ===> Add another? Yes\
?       Secret 7 spTenantId\
?       Value <<EXTRACTED>>\
? ===> Add another? No\
? Where should the project's shared secret come from? Specify my own\
? Shared Secret <<EXTRACTED>>\
? Configure GitHub Access? No\
? Configure advanced options No\
Project ID: brigade-c0e1199e88cab3515d05935a50b300214e7001610ae42fae70eb97

## Setup ACR WebHook

Now we have everything setup, the only thing that is missing is to make sure that your Brigade project is kicked off every time a new image is pushed to the container registry. To do this, navigate to your Azure Container Registry and select the **Webhooks** tab. Create a new webhook, and point it to the IP address of your container registry gateway that you noted before.

Note the format of the URL, read more about the Brigade container registry here: <https://docs.brigade.sh/topics/dockerhub/>

**Creating an ACR webhook**

[![image_thumb[1]](image_thumb1_thumb.png "image_thumb[1]")](image_thumb1.png)

To only receive events from one specific repository, I have specified the Scope property and set it to **acrdemo:***, which effectively filters out all other push events.

## Trying it out

Let’s see if this works then, shall we? I’m pushing a new version of my demo images (jakob.azurecr.io/acrdemo:1.17) , and then run the Brigade dashboard (brig dashboard).

I can see that a build has been kicked off for my project, and the result looks like this:

[![image_thumb[4]](image_thumb4_thumb.png "image_thumb[4]")](image_thumb4.png)

I can see that I got a image_push event and that the build contained one job called purge (that name was specified in the Javascript pipeline when creating the job). We can drill down into this job and see the output from the script that was executed:

[![image_thumb[5]](image_thumb5_thumb.png "image_thumb[5]")](image_thumb5.png)

Since I specfied minImageToKeep to 5, the script now deleted version 1.12 (leaving the 5 latest versions in the repository).

Hope you found this valuable!

\

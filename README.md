# openshift-intern-workshop

### Install OpenShift client tools

Install via DNF

```
dnf install origin-clients
```

or donwload from Github - https://github.com/openshift/origin/releases/tag/v3.11.0

### Get code

Fork this repository (https://github.com/vpavlin/openshift-intern-workshop/fork) and clone it to your machine

### Login to the OpenShift cluster

You can either use your username and password

```
oc login https://<CLUSTER_URL>:8443 -u <USERNAME>
```

or you can use authentication token. To get a token, go to OpenShift Console, login, click your username in the top right corner and click *Copy Login Command*.

The whole command will be copied and you only need to paste it in the terminal and run it.

### Install Python ecosystem specific packaging tools

To be able to install pre-commit package bellow, you will need a tool `pip`

```
dnf install python-pip
```

### Configure pre-commit

[Pre-commit](https://pre-commit.com) as a framework for managing and maintaining multi-language pre-commit hooks. The tool is very useful when you are submitting changes to your or upstream repositories as it'll help you to keep the code clean and prevent many potential issues which might be noticed during review or not at all.

To install pre-commit, run

```
pip install --user pre-commit
```

Take a look at the file `.pre-commit-config.yaml` which contains configuration for pre-commit used in this repository.

To install the pre-commit hooks to your git repository run

```
pre-commit install
```

Now every time you do a git commit a set of checks will be run against your changes and errors will be reported and some even fixed automatically.

### Deploy the application

We need to deploy our application now. To verify you are successfully logged into OpenShift, you can run a following command

```
oc project
```

OpenShift/Kubernetes use JSON and YAML format to describe the deployment artifacts. You can find all the artifacts in YAML format in `openshift/` directory

To deploy whole application, you can pass a directory to oc **apply** command:

```
oc apply -f openshift/
```

Go to OpenShift Console and you should see a **build** running. Wait for the build to finish and for the deployment to proceed. Then try to access the **route** URL

### Fix the port

If you tried to access the application URL you were probably presented with *Application is not available" error. This could happen from various reasons, but the first thing we can check is whether our hostname and port in Flask application are configured properly.

Look at the last line in `app.py` file - you'll see we load the port from environment variable or use port `5000` as a default. Also look at the deployment config in `openshift/app.deploymentconfg.yaml` and focus on 2 things:

* a field `containerPort` in containers section
* an environment variabe `PORT`

As you can see these do not match. As changing `containerPort` would also require changing the **service** ports definition, we'll go for the envirnment variable and change it to `8080` to match the exposed port. We need to update the deployment config in the cluster. We can do this by running

```
oc apply -f openshift/app.deploymentconfig.yaml
```

Once the application is redeployed, you should get response like this:

```
{"msg":"Forbidden","status":403}
```

### Service account & roles

To get through the authentication you need to provide the URL with a secret in a query parameter, so try to add `?secret=secret` to the application address.

Internal server error - that does not look good - what have we missed. Let's inverstigate logs again - go to OpenShift Console and view the pod logs.

You will see something like the following error among the log messages:

```
HTTP response body: b'{"kind":"Status","apiVersion":"v1","metadata":{},"status":"Failure","message":"pods is forbidden: User \\"system:serviceaccount:vpavlin-os-ws:default\\" cannot list pods in the namespace \\"vpavlin-os-ws\\": no RBAC policy matched","reason":"Forbidden","details":{"kind":"pods"},"code":403}\n'
```

This is becuase our application is trying to access OpenShift API without proper authorization (you can see authentication is ok - OpenShift recognized the provided service account, but it does not have the correct rights to access resources it is trying to access).

We need to add a correct **role** to our service account. You can see the error mentions service account (or SA) **default**- The best practice would be to create a separate SA for this use case, but let's just change the default one for now.

We will need to add a **view** role for the SA and we can do this by running the following command

```
oc adm policy add-role-to-user view -z default
```

If the command succeeded, you will be able to reload the app URL and get back a JSON response.


### Change default secret

Let's look at **secrets** now. Secrets and Config Maps are resources used for app configuration. Our application uses one secret as well - `openshift/app.secret.yaml`. Take a look at it.

The interesting part is in section `data`, but you cannot easily read it. The secret is obfuscated by **base64** encoding to make it slightly harder to leak it by showing to someone. If we want to read it, we can copy the value and pass it through the base64 decoder

```
echo "c2VjcmV0" | base64 -d
```

So the actual value is `secret`. Let's change it now! Pick a new secret and use it in following command

```
echo -n "<MYNEWSECRET>" | base64
```

Now copy the value and edit the secret in OpenShift

```
oc edit secret openshift-intern-workshop
```

Look at the file `openshift/app.deploymentconfig.yaml` and try to find how the secret is used there.

As secrets and config maps are mainly used in environment variables (which cannot be changed dynamically at runtime from outside of the container), we need to re-deploy our application to pick up new secret.

```
oc rollout latest openshift-intern-workshop
```

Once the deployment is finished, you will need to provide a new secret in the URL to be able to access the application.

### Health checks

OpenShift/Kubernetes come with a feature called health checks. There are 2 kinds of health checks - readiness and liveness probe. These are very important for lifecycle management of your application.

Readiness probe is a check which verifies if your application is fully up and running and ready to accept requests.

Liveness probe is used after readiness probe succeeds to verify application is still fully up and alive.

If something fails in the container without actually failing the whole container or pod, you app may end up in inconsistent state. The simplest way to get to a consistent state is to restart the application - if readiness or liveness probe fail, OpenShift will restart the pod to get to a consistent state.

#### Readiness Probe

Go to OpenShift Console > Applications > Deployments > openshift-intern-workshop. Then select Actions > Edit Health Checks on the right. Click Add Readiness Probe.

Look at the `app.py` - which of the API calls would you use for this (hint: health)? Add the path (including leading forward slash) to the Path field. You can leave the rest as is. Click Save.

Once your application is redeployed it will verify it is started up properly before OpenShift sends any traffic to the pod.

#### Liveness Probe

Let's add the Liveness Probe the hard way:). Go back to OpenShift Console > Applications > Deployments > openshift-intern-worksho again, but this time click Actions > Edit YAML.

Find the `readinessProbe` section, duplicate it and change the name to `livenessProbe`. Make sure the indentation is the same and you pasted the whole block right below the readiness probe block.

Click Save and wait for a new deployment. If you go to Applications > Pods and open the latest openshift-intern-workshop pod, you should see both readiness and liveness probes mentioned on the right

```
Readiness Probe: GET /health on port 8080 (HTTP) 1s timeout
Liveness Probe: GET /health on port 8080 (HTTP) 1s timeout
```

### Changing the code

Our application uses Source-To-Image (or S2I). S2I is a smart tool which makes it easy to build application container images. Look at the `openshift/app.buildconfig.yaml` to see how the S2I strategy is configured.

You can notice we need to provide 3 pieces of information

* Source image
* Source repository
* Output image

Source image is a contiainer image which was designed for working with S2I - in other words contains `assemble` and `run` scripts - you can see and example here: https://github.com/sclorg/s2i-python-container/blob/master/3.6/s2i/bin/assemble

Source repository is a git repository containing application in a language matching the one of a source container image, so that the tools in the source image know how to install the application.

Output image is a name of an image stream where the resulting container image will be pushed.

To be able to successfully build from your own repository, do not forget to change the *build config* source repository to your own!

#### Building from local directory

When you develop your code you will need to rebuild the container image for your application. Our application was originally built and deployed from a git repository. To be able to quickly rebuild your knew changes you might want to skip the step of pushing your code to a repository and then kicking off the build.

To do that, you can use (make sure you are in the root of the repository)

```
oc start-build openshift-intern-workshop --from-dir=. -F
```

Start build command will start new build in OpenShift and `--from-dir` will collect contents of a given directory, compress it and send it to OpenShift as a context directory for the new build. Parameter `-F` fill redirect logs from the build to the terminal, so that you can easily look at how the build progresses.

Once the build is finished, OpenShift will automatically redeploy our application - this happens based on **triggers** defined in `openshift/app.deploymentconfig.yaml`

#### Setting up webhooks

Webhooks are a powerfull automation feature provided by both - OpenShift and Github. OpenShift will act as a reciever of a webhook request and Github will produce webhook calls when we push to the repository.

First go to OpenShift Console > Builds > Builds > openshift-intern-workshop > Configuration and copy the *Github Webhook URL*.

Next go to your Github wokrshop repository and click Setting > Webhooks > Add webhook. Paste the copied URL in *Payload URL*, change *Content type* to `application/json` and disable *SSL verification* and confirm by clicking *Add webhook*.

### Add services to response

Create a new branch in your repository

```
git checkout -b feature/services
```

Look at the code in `workshop/openshift_info.py` and try to add a method similar to `get_pods`, but instead of a list of Pod names, make it to return list of Service names

<details><summary>Solution</summary>
<p>

```python
    def get_services(self):
        services_api = self.oapi_client.resources.get(kind='Service', api_version='v1')
        service_list = services_api.get(namespace=self.namespace)
        return self._get_names(service_list)
```

</p>
</details>


# Tasks


## Add a PVC and persist the "iam" file
## Fix inconsistent return type in API methods

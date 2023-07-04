# Prerequisites    
- Kubernetes cluster must be on the running stage (Kubernetes 1.26+)     
- Helm 3.1.0      

# Installing the Charts    

## Installing Nginx Ingress Controller 

The Ingress is a Kubernetes resource that lets you configure an HTTP load balancer for applications running on Kubernetes, represented by one or more Services. Such a load balancer is necessary to deliver those applications to clients outside of the Kubernetes cluster

The Ingress resource supports the following features:

⦿  Content-based routing:

- `Host-based routing:` For example, routing requests with the host header foo.example.com to one group of services and the host header bar.example.com to another group.

- `Path-based routing:` For example, routing requests with the URI that starts with /serviceA to service A and requests with the URI that starts with /serviceB to service B.

⦿ **TLS/SSL** termination for each hostname, such as foo.example.com.

Before installing Iris-web install the Nginx ingress controller
```
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm install my-release ingress-nginx/ingress-nginx -n <Name_Space>
```
> **Info**: `my-release` is the name that you choose

## Installing Iris Web

Clone this Repository       
```bash     
$ git clone https://github.com/dfir-iris/iris-web.git      
```      


To install the chart with the release name `my-release`:      
```bash    
$ helm install my-release charts/ --values charts/values.yaml  -n <Name_Space>  
```      
The command deploys **iris-web** on the Kubernetes cluster in the default configuration.  

## Checking Dependencies

To check if Helm and kubectl are installed, run the following command:

```
make check-dependencies
```
If any of the dependencies are missing, the corresponding installation command will be executed automatically.

## Installing Iris
To install Iris, run the following command:
```
make install-iris
```

This will upgrade or install the Iris application using Helm. The installation uses the provided charts/values.yaml file and installs it in the specified namespace.

Replace `<name_space>` with the desired namespace for the Iris application.

## Deleting Iris
To delete the Iris application, run the following command:
```
make delete-iris
```
This will delete the Iris application using Helm. The application will be removed from the specified namespace.

Replace `<name_space>` with the namespace where the Iris application is installed.

> **Tip**: List all releases using `helm list`  

# Uninstalling the Charts    

To uninstall/delete the `my-release` deployment:      

The command removes all the Kubernetes components associated with the chart and deletes the release.      

```bash     
$ helm delete my-release -n <Name_Space>   
``` 
# Parameters    
The [Parameters](#parameters) section lists the parameters that can be configured during installation.

### Common parameters       
| Name | Description | Value |     
| --| -- | -- |     
| `replicaCount` | Number of Iris replicas to deploy | `1` |     


### Lable parameters
| Name | Description | Value |     
| --| -- | -- |     
| `app` | Define metadata app name	 | `string` |  
| `name` | Define lables name		 | `string` | 


### Image parameters     
Using Dockerfile or Docker compose create images for Iris and apply image to their respective yaml file.
> **Note**: For kubernetes  use modified Dockerfile.k8s file to create an images

| Name | Description | Value |      
| --| -- | -- |      
| `image.repository` | Iris image repository | `string` |       
| `image.tag` | Iris image tag  | `latest` |        
| `image.pullPolicy` | Iris image pull policy | `string` |       
   

### Service parameters
| Name | Description | Value |     
| --| -- | -- |     
| `service.type` | Iris service type | `LoadBalancer`|     
| `service.port` | Iris service port | `80` |       

## Ingress parameters
| Name | Description | Value |     
| --| -- | -- |     
| `host_name` | Hostname for Iris app | `string`|     
  
## How to expose the application?

List the Ingress resource on the Kubernetes cluster
```
kubectl get ingress -n <Name_Space>
```
Expose the application with your Hostname
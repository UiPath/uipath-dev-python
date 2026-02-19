param(
    [Parameter(Mandatory)]
    [string] $resourceGroupName,

    [Parameter(Mandatory)]
    [string] $appName,

    [Parameter(Mandatory)]
    [string] $acrName
)

$imageName = "uipath-dev-python:$(Get-Date -Format 'yyyyMMddHHmmss')"
$acrImageName = "$($acrName).azurecr.io/$($imageName)"

az acr login --name $acrName

docker build -t $imageName $PSScriptRoot
docker tag $imageName $acrImageName
docker push $acrImageName

az webapp config container set `
  --resource-group $resourceGroupName `
  --name $appName `
  --container-image-name $acrImageName

az webapp restart `
  --resource-group $resourceGroupName `
  --name $appName

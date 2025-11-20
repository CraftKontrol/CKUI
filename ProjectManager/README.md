# Project Manager
## Version 1.027
### Author: Arnaud Cassone © Artcraft Visuals
It's a TouchDesigner project configurator tool that helps manage project dependencies, configurations, and repositories. 
It provides an easy way to set up and maintain a TouchDesigner projects with the necessary packages and settings.

It does the following:
- Check for saved project location / Open Popup to set project location if not found
- Check for Logger installation paths / Set Logger path if not found
- Check for config.json file / Create config.json file if not found
- Check for gitignore file / Create gitignore file if not found
- Check for git installation / Install git if not found
- Check for libraries folder
- Clone required libraries on demand
- Show IP addresses for local network access
- Check for WebLogger module installation

## Parameters
| Parameter | Type | Description |
|----------------------|------|---------------------------------|
|Info|Str||
|Manualsetup|Pulse||
|Logger|Str||
|Systeminfos|Header||
|Ipaddress1|Str||
|Ipaddress2|Str||
|Librariesheader|Header||
|Libraries|Folder||
|Ckui|Str||
|Downloadckui|Pulse||
|Ggen|Str||
|Downloadggen|Pulse||
|Terrain|Str||
|Downloadterrain|Pulse||
|Baseversion|Str||
|Installpython|Pulse||
|Pythonversion|Str||
|Venv|Header||
|Status|Str||
|Createvenv|Pulse||
|Version|Menu||
|Venvfolder|Folder||
|Pip|Header||
|Pipinstallpackage|Pulse||
|Package|Str||
|Cktdlibrary|Str||
|Downloadcktd|Pulse||
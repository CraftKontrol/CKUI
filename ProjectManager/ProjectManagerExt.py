"""
Project Manager Extension for TouchDesigner
Author: Arnaud Cassone / CraftKontrol
It manages project setup, library paths, and dependencies.
"""

import json
from threading import local
from TDStoreTools import StorageManager
import TDFunctions as TDF
import os
import pip
import subprocess
import socket 
import datetime
import json
import urllib.request
import os
import sys


class ProjectManagerExt:
	"""
	ProjectManagerExt description
	"""
	def __init__(self, ownerComp):
		# The component to which this extension is attached
		self.ownerComp = ownerComp
		# properties
		TDF.createProperty(self, 'State', value='Startup', dependable=True,readOnly=False)
		TDF.createProperty(self, 'PythonPath', value='Unknown', dependable=True,readOnly=False)
		TDF.createProperty(self, 'VenvStatus', value='Unknown', dependable=True,readOnly=False)
		TDF.createProperty(self, 'VenvPath', value='Unknown', dependable=True,readOnly=False)
		TDF.createProperty(self, 'VenvPythonExe', value='Unknown', dependable=True,readOnly=False)
		TDF.createProperty(self, 'Logger', value='Unknown', dependable=True,readOnly=False)
		TDF.createProperty(self, 'IpAddresses', value=[], dependable=True,readOnly=False)
		TDF.createProperty(self, 'CKUI', value='Unknown', dependable=True,readOnly=False)
		TDF.createProperty(self, 'CKTDLibrary', value='Unknown', dependable=True,readOnly=False)
		TDF.createProperty(self, 'GGEN', value='Unknown', dependable=True,readOnly=False)
		TDF.createProperty(self, 'TerrainTools', value='Unknown', dependable=True,readOnly=False)
		TDF.createProperty(self, 'CKUIColor', value=(0,0.5,1), dependable=True,readOnly=False)
		# attributes:
		self.a = 0 # attribute
		self.B = 1 # promoted attribute

		# stored items (persistent across saves and re-initialization):
		storedItems = [
			# Only 'name' is required...
			{'name': 'StoredProperty', 'default': None, 'readOnly': False,
			 						'property': True, 'dependable': True},
		]
		# Uncomment the line below to store StoredProperty. To clear stored
		# 	items, use the Storage section of the Component Editor
		
		# self.stored = StorageManager(self, ownerComp, storedItems)

	def myFunction(self, v):
		debug(v)
		


	def OnCreate(self):
		self.OnStart()

	def OnStart(self):
		
		# check if venv is active
		venvFolder = parent().par.Venvfolder.eval()
		if os.path.exists(venvFolder):
			op.Logger.Info(me,"Virtual environment folder found at: {}".format(venvFolder))
			try:
				venvPythonExe = os.path.join(venvFolder, 'Scripts', 'python.exe')
				result = subprocess.run([venvPythonExe, '--version'], capture_output=True, text=True, check=True)
				venvPythonVersion = result.stdout.strip()
				op.Logger.Info(me, f"Virtual environment Python version: {venvPythonVersion}")
			except Exception as e:
				op.Logger.Warning(me, f"Failed to get Python version from venv: {e}")
				venvPythonVersion = 'Unknown'
		
			self.VenvStatus = venvPythonVersion  + " in /" + venvFolder
			self.VenvPythonExe = os.path.join(venvFolder, 'Scripts', 'python.exe')
		else:
			op.Logger.Warning(me,"Virtual environment not found at: {}".format(venvFolder))
			self.VenvStatus = 'not Found'

		# set main project name to the Overall CKUI System name
		if op('/project1') is not None:
			op('/project1').name = 'MainProject'
			op('/perform').par.winop = '/MainProject'
		
		# open a popup window to choose a project folder and name
		if 'NewProject' in project.name:
			self.OpensaveDialog()  
		else:
			self.Setup()

	def OpensaveDialog(self):
		# open the save dialog
		op('Dialogs/ProjectSaveDialog').par.Open.pulse()

	def SavePropject(self):
		# save the current project
		project.save()
 
	def Setup(self):
		op.Logger.Info(me,"Setup Project Manager...")
		self.State = 'Setup'
		self.InitializeLogger()
		self.CheckConfig()
		self.CheckGitignore()
		self.UpdateLibraries()
		self.CheckDependencies()
		self.GetSystemInfo()
		self.SetColors()
		op.Logger.Info(me,"Project Manager Ready.") 
		self.State = 'Ready'
		pass
	
	def GetLocalIP(self):
		hostname = socket.gethostname()    
		IPAddr4 = socket.gethostbyname_ex(hostname)  
		Addresses = []
		for addr in IPAddr4[2]:
			if '.' in addr:
				Addresses.append(addr)
		return Addresses
	
	def GetSystemInfo(self):
		Addresses = self.GetLocalIP()
		# Check if parameters exists then delete them
		for par in parent().pars():
			if par.name.startswith('Ipaddress'):
				par.destroy()

		IpAddresses = [] 
		# Store IP addresses in the list
		for i, addr in enumerate(Addresses):
			self.IpAddresses.append(addr)

		# Create parameters for each IP address
		for i in range(len(self.IpAddresses)): 
			ipPar = parent().customPages[0].appendStr('Ipaddress'+ str(i+1))
			ipPar.default = self.IpAddresses[i]
			ipPar.reset() 
			ipPar.readOnly = True 
			ipPar.order = 4

		op.Logger.Info(me,"System IP Addresses: {}".format(Addresses)) 

	def CheckConfig(self):
		# Check if the config file is present, if not create it
		ProjConfig = self.ownerComp
		configFilePath = project.folder + '/config.json'
		if os.path.exists(configFilePath):
			op.Logger.Info(me,"Config file found: {}".format(configFilePath))
		else:
			
			self.SaveConfig()

	def SaveConfig(self):
		# Save the current configuration to a json file
		ProjConfig = self.ownerComp
		config = {
			"Project": project.name.split('.')[0].strip(),
			"ToolsPath": ProjConfig.par.Libraries.eval(),
			"LogPath": op.Logger.par.Logfolder.eval(),
			"TouchDesignerVersion": app.build,
			"Modules": {},
			"Properties": {}
			
		}
		configFilePath = project.folder + '/config.json'
		try:
			with open(configFilePath, 'w') as configFile:
				json.dump(config, configFile, indent=4)
		except Exception as e:
			op.Logger.Error(me,"Failed to save config file: {}".format(e))
			return
		op.Logger.Info(me,"Config file saved: {}".format(configFilePath))

	def CheckGitignore(self):
		# Check if .gitignore file exists in the project folder
		# ignore iterations (projectname.4.toe) to projectname.toe
		
		gitignorePath = os.path.join(project.folder, '.gitignore') 
		projectName = project.name.split('.')[0].strip()


		if not os.path.exists(gitignorePath):
			# create a .gitignore file
			with open(gitignorePath, 'w') as f:
				f.write('*.toe\n')
				f.write('!' + projectName + '.toe\n')
				f.write('Logs/\n')
				f.write('log/\n')
				f.write('Backup/*\n')
				f.write('config.json\n')
				f.write('custom_operators.tox\n')
				f.write('*.bak\n')
				f.write('*.dmp\n')
				f.write('*.pyc\n')
				
			op.Logger.Info(me,".gitignore file created")
		else:
			op.Logger.Info(me,"Project .gitignore exists")
		pass
	
	def InitializeLogger(self):
		
		# Check if WebLogger is present
		if hasattr(op, 'WebLogger'): 
			pass
		
  

		# Initialize the logger
		op.Logger.par.Logfolder = project.folder + '/Logs' 
		op.Logger.par.Active = True 
		op.Logger.par.Logtofile = True
		op.Logger.allowCooking = True
		
		parent().par.Logger = "Ready"
		op.Logger.Info(me,"Logger Initialized.")
		pass
	
	def UpdateLibraries(self):
		# Update the project library path
		self.ProjectLibPath = parent().par.Libraries.eval()

		# Check for the libraries in the project library path
		self.CKUI = 'Not Found'
		self.CKTDLibrary = 'Not Found'
		self.GGEN = 'Not Found'
		self.TerrainTools = 'Not Found'

		for folder in os.listdir(self.ProjectLibPath):
			folderPath = os.path.join(self.ProjectLibPath, folder)
			if os.path.isdir(folderPath):
				if folder.lower().find('ckui') != -1:
					self.CKUI = "Ready"
				elif folder.lower().find('td-library') != -1:
					self.CKTDLibrary = 'Ready'
				elif folder.lower().find('groundgen') != -1:
					self.GGEN = "Ready"
				elif folder.lower().find('terrain-tools') != -1:
					self.TerrainTools = "Ready"
		
		op.Logger.Info(me,"Libraries Checked")
		pass

	def CheckDependencies(self):
		# get global python path
		for path in sys.path:
			if 'Lib/site-packages' in path:
				self.PythonPath = path
				# op.Logger.Info(me,"Python site-packages path: {}".format(self.PythonPath))
				break

			
		if self.PythonPath != 'Unknown':
			
			# check if git is installed
			git = False
			try:
				import git
				# op.Logger.Info(me,"Git is already installed.")
				git = True
			except ImportError:
				op.Logger.Info(me,"Git not found, installing...")
				try:
					subprocess.run(['python', '-m', 'pip', 'install', 'GitPython'], check=True)
					git = True
					pass
				except Exception as e:
					op.Logger.Info(me,"Failed to install Git: {}".format(e))
					return
				
		op.Logger.Info(me,"All dependencies are met.")
		
	def DownloadLibrary(self, libName):
		# Download the specified library from Github
		import git
		if libName == 'CKUI':
			repoName = 'CKUI'
			repoURL = 'https://github.com/CraftKontrol/CKUI.git'
			op.Logger.Info(me,"Cloning repository {} from {}".format(repoName, repoURL))
			try:
				subprocess.run(['git', 'clone', repoURL, os.path.join(self.ProjectLibPath, repoName)], check=True)
				op.Logger.Info(me,"Repository {} cloned successfully.".format(repoName))
				self.CKUI = 'Ready'
			except Exception as e:
				op.Logger.Info(me,"Failed to clone repository {}: {}".format(repoName, e))

		elif libName == 'GGEN':
			repoName = 'GroundGen-for-Touchdesigner'
			repoURL = 'https://github.com/CraftKontrol/GroundGen-for-Touchdesigner.git'
			op.Logger.Info(me,"Cloning repository {} from {}".format(repoName, repoURL))
			try:
				subprocess.run(['git', 'clone', repoURL, os.path.join(self.ProjectLibPath, repoName)], check=True)
				op.Logger.Info(me,"Repository {} cloned successfully.".format(repoName))
				self.GGEN = 'Ready'
			except Exception as e:
				op.Logger.Info(me,"Failed to clone repository {}: {}".format(repoName, e))
			
		elif libName == 'TerrainTools':
			repoName = 'Terrain-Tools-for-Touchdesigner'
			repoURL = 'https://github.com/CraftKontrol/Terrain-Tools-for-Touchdesigner.git'
			op.Logger.Info(me,"Cloning repository {} from {}".format(repoName, repoURL))
			try:
				subprocess.run(['git', 'clone', repoURL, os.path.join(self.ProjectLibPath, repoName)], check=True)
				op.Logger.Info(me,"Repository {} cloned successfully.".format(repoName))
				self.TerrainTools = 'Ready'
			except Exception as e:
				op.Logger.Info(me,"Failed to clone repository {}: {}".format(repoName, e))
			pass
		elif libName == 'CKTDLibrary':

			repoName = 'TD-Library'
			repoURL = 'https://github.com/CraftKontrol/TD-Library.git'
			op.Logger.Info(me,"Cloning repository {} from {}".format(repoName, repoURL))
			try:
				
				subprocess.run(['git', 'clone', repoURL, os.path.join(self.ProjectLibPath, repoName)], check=True)
			
				op.Logger.Info(me,"Repository {} cloned successfully.".format(repoName))
				self.CKTDLibrary = 'Ready'
			except Exception as e:
				op.Logger.Info(me,"Failed to clone repository {}: {}".format(repoName, e))
			pass

		
		pass
	
	def LogMessage(self, info):
		# Log message to WebLogger if available
		if hasattr(op, 'WebLogger'):
			date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
			level = info['logItemDict']['level']
			message = info['logItemDict']['message'] #Raw message
			traceback = message.split('-')[0].strip().split('path:')[1].strip()
			node = op(traceback) # Get the operator from the path
			node = node.name # Get the operator name
			text = message.split('-')[1].strip() # Extract the actual log message
			# format the info dict to send to WebLogger in json
			infos = {"type": "error", "errorType": level, "errorMsg": text, "errorSrc": node, "traceback": traceback, "date": date}
			# Send the log message to WebLogger via WebSocket
			op.WebLogger.op('webserver1').webSocketSendText(op.WebLogger.op('table_clients')[1,0], json.dumps(infos))
			return
		
	def DownloadInstallPython(self, version):
		# Download and install the specified Python version
		if version == "":
			return
		

		#check if thsis version is already installed in LOCALAPPDATA or in PROGRAMFILES
		local = os.path.join(os.getenv('LOCALAPPDATA'), 'Programs', 'Python', 'Python' + str(version).replace('.', '')[:-1])
		programs = os.path.join(os.getenv('PROGRAMFILES'), 'Python' + str(version).replace('.', '')[:-1])

		localExists = os.path.exists(local)
		programsExists = os.path.exists(programs)

		# check if is on PATH
		sysPath = os.environ['PATH']

		if not localExists and not programsExists:
			op.Logger.Info(me,f"Python {version} is not installed, Downloading and Installing...")
			
			# Determine the download URL based on win 64bit
			downloadURL = f"https://www.python.org/ftp/python/{sys.version}/python-{sys.version}-amd64.exe"
			installerPath = os.path.join(os.getenv('TEMP'), f'python-{sys.version}-amd64.exe')
			try:
				# Download the installer
				urllib.request.urlretrieve(downloadURL, installerPath)
				op.Logger.Info(me,f"Downloaded Python {version} installer.")
				
				# Run the installer silently
				subprocess.run([installerPath, 'InstallAllUsers=1', 'PrependPath=1'], check=True)
				op.Logger.Info(me,f"Python {version} installed successfully.")

				
			except Exception as e:
				op.Logger.Error(me,f"Failed to download or install Python {version}: {e}")

		else:
			op.Logger.Info(me,f"Python {version} is already installed.")
		# check add to PATH
		if localExists:
			if local in sysPath:
				op.Logger.Info(me,f"Python {version} is already on PATH.")
			else:
				op.Logger.Info(me,f"Python {version} is not on PATH, Adding...")
				# add it to PATH
				os.environ['PATH'] += ';' + local
		if programsExists:
			if programs in sysPath:
				op.Logger.Info(me,f"Python {version} is already on PATH.")
			else:
				op.Logger.Info(me,f"Python {version} is not on PATH, Adding...")
				# add it to PATH
				os.environ['PATH'] += ';' + programs

		self.find_all_python_executables()
		
		pass

	def find_all_python_executables(self):
		
		possible_paths = [
			f"C:/Python{sys.version_info.major}{sys.version_info.minor}/python.exe",
			f"C:/Program Files/Python{sys.version_info.major}{sys.version_info.minor}/python.exe",
			f"C:/Program Files (x86)/Python{sys.version_info.major}{sys.version_info.minor}/python.exe",
			f"C:/Users/{os.getlogin()}/AppData/Local/Programs/Python/Python{sys.version_info.major}{sys.version_info.minor}/python.exe",
		]

		path_env = os.environ.get('PATH', '')

		for path in path_env.split(os.pathsep):
			python_exe_path = os.path.join(path, 'python.exe')
			if os.path.isfile(python_exe_path):
				possible_paths.append(python_exe_path)

			python_executables = [path for path in possible_paths if os.path.exists(path)]
			self.ownerComp.par.Version.menuNames = python_executables

			python_labels = []
		for path in python_executables:
			if 'Python' in path:
				python_labels.append('Python' + path.split('Python')[-1].split('/')[0])
			else:
				python_labels.append(os.path.basename(path))
			self.ownerComp.par.Version.menuLabels = python_labels

	def CreateVenv(self):
		
		version = parent().par.Version.eval() # ex python39/python.exe
		#check if thsis version is already installed in LOCALAPPDATA or in PROGRAMFILES
		possible_paths = [
			f"C:/Program Files/",
			f"C:/Users/{os.getlogin()}/AppData/Local/Programs/Python/",
		]

		#check if version is on possible paths
		pythonExe = 'Unknown'
		for basePath in possible_paths:
			pythonPath = os.path.join(basePath, version)
			
			if os.path.exists(pythonPath):
				pythonExe = pythonPath
				break

		if pythonExe == 'Unknown':
			op.Logger.Warning(me,"Desired Python version not found: {}".format(version))
			self.VenvStatus = 'Failed'
			return
		
		# create the venv

		venvFolder = parent().par.Venvfolder.eval()
		if venvFolder == '':
			op.Logger.Warning(me,"Venv folder name is empty.")
			return
		venvPath = os.path.join(project.folder, venvFolder)
		if not os.path.exists(venvPath):
			op.Logger.Info(me,"Creating virtual environment at: {}".format(venvPath))
			try:
				subprocess.run([pythonPath, '-m', 'venv', venvPath], check=True)
				op.Logger.Info(me,"Virtual environment created successfully.")
				self.VenvStatus = 'Ready'
			except Exception as e:
				op.Logger.Error(me,"Failed to create virtual environment: {}".format(e))
		else:
			op.Logger.Info(me,"Virtual environment already exists at: {}".format(venvPath))
			self.VenvStatus = 'Ready'

		self.VenvPythonExe = os.path.join(venvFolder, 'Scripts', 'python.exe')


			# add it to PATH
		if venvPath not in os.environ['PATH']:
			os.environ['PATH'] += ';' + venvPath
			op.Logger.Info(me,"Virtual environment added to PATH.")
			#add scripts folder too
			os.environ['PATH'] += ';' + os.path.join(venvPath, 'Scripts')
		try:
			venvPythonExe = os.path.join(venvFolder, 'Scripts', 'python.exe')
			result = subprocess.run([venvPythonExe, '--version'], capture_output=True, text=True, check=True)
			venvPythonVersion = result.stdout.strip()
			op.Logger.Info(me, f"Virtual environment Python version: {venvPythonVersion}")
			self.VenvStatus = venvPythonVersion + " in /" + venvFolder
		except Exception as e:
			op.Logger.Warning(me, f"Failed to get Python version from venv: {e}")
			venvPythonVersion = 'Unknown'

		
		#Install pip in the venv
		try:
			subprocess.run([self.VenvPythonExe, '-m', 'ensurepip'], check=True)
			op.Logger.Info(me,"pip installed in virtual environment.")
		except Exception as e:
			op.Logger.Error(me,"Failed to install pip in virtual environment: {}".format(e))

	def PipInstallPackage(self, packageName):
		# Install the specified package in the virtual environment
		packageName = str(packageName)
		if self.VenvPythonExe == 'Unknown':
			op.Logger.Warning(me,"Virtual environment Python executable not found.")
			return
		try:
			subprocess.run([self.VenvPythonExe, '-m', 'pip', 'install', packageName], check=True)
			op.Logger.Info(me,"Package {} installed successfully in virtual environment.".format(packageName))
		except Exception as e:
			op.Logger.Error(me,"Failed to install package {}: {}".format(packageName, e))

	def SetColors(self):
		# Set colors of all nodes in the project to CKUIColor
		# not for nodes inside components named 'Content'
		# not for nodes inside components with tag 'CKLib'
		# recursively exclude those nodes
		ckColor = self.CKUIColor
		for node in op('/MainProject').findChildren():
			exclude = False
			if 'CKLib' in node.tags:
				exclude = True
			parentComp = node.parent()
			try:
				while parentComp is not None:
					if parentComp.name == 'Content' or 'CKLib' in parentComp.tags:
						exclude = True
						break
					parentComp = parentComp.parent()
			except:
				pass
			if not exclude:
				# Set the node color
				node.color = ckColor

				# set Icon color if exists
				if node.name == 'ico':
					node.par.fontcolorr = ckColor[0]
					node.par.fontcolorg = ckColor[1]
					node.par.fontcolorb = ckColor[2]
			
		


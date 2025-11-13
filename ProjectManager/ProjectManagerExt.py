"""
Project Manager Extension for TouchDesigner
Author: Arnaud Cassone / CraftKontrol
It manages project setup, library paths, and dependencies.
"""

from TDStoreTools import StorageManager
import TDFunctions as TDF
import os
import pip
import subprocess

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
		TDF.createProperty(self, 'ProjectLibPath', value='Unknown', dependable=True,readOnly=False)
		TDF.createProperty(self, 'Logger', value='Unknown', dependable=True,readOnly=False)
		TDF.createProperty(self, 'CKUI', value='Unknown', dependable=True,readOnly=False)
		TDF.createProperty(self, 'CKTDLibrary', value='Unknown', dependable=True,readOnly=False)
		TDF.createProperty(self, 'GGEN', value='Unknown', dependable=True,readOnly=False)
		TDF.createProperty(self, 'TerrainTools', value='Unknown', dependable=True,readOnly=False)
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
		self.CheckGitignore()
		self.UpdateLibraries()
		op.Logger.Info(me,"Project Manager Ready.")
		self.State = 'Ready'
		pass
	
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
				f.write('Backup/*')
			op.Logger.Info(me,".gitignore file created at: {}".format(gitignorePath))
		else:
			op.Logger.Info(me,".gitignore file already exists at: {}".format(gitignorePath))
		pass
	
	def InitializeLogger(self):
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
		
		self.CheckDependencies()
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



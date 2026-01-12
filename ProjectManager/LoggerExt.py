"""
Extension classes enhance TouchDesigner components with python. An
extension is accessed via ext.ExtensionClassName from any operator
within the extended component. If the extension is promoted via its
Promote Extension parameter, all its attributes with capitalized names
can be accessed externally, e.g. op('yourComp').PromotedFunction().

Help: search "Extensions" in wiki
"""

import inspect
import logging
from logging.handlers import TimedRotatingFileHandler
import os
import pathlib
from typing import Dict
from TDStoreTools import StorageManager
TDF = op.TDModules.mod.TDFunctions
import subprocess
import platform
import requests
from ckserverapi import CKServerApi

BASE = "https://www.artcraft-zone.com/CK"
TOKEN_LOG = parent().par.Tokenlog.eval()
TOKEN_SYNC = parent().par.Tokensync.eval()
TOKEN_ADMIN = parent().par.Tokenadmin.eval()

client = CKServerApi(BASE, TOKEN_LOG, TOKEN_SYNC, TOKEN_ADMIN)

class LoggerExt:
	"""
	LoggerExt description
	"""
	def __init__(self, ownerComp):
		"""
		The LoggerExt constructor drives the Logger COMP
		and exposes various promoted methods in addition to holding essential data to the Logger COMP instance and the logging library.

		Args:
			ownerComp (COMP): The current Logger COMP to which this extension is attached.
		"""
		self.ownerComp = ownerComp
		self.aboutPageUpdate()

		self.Active = self.ownerComp.par.Active.eval() 

		self.isLoggingEnvVarPassed = True if 'TOUCH_SYS_LOG_LEVEL' in os.environ.keys() else False
		
		# TDAppLogger is the main root logger, TDSysLogger is parented to it.
		self.inTDAppLogger = self.isTDAppLogger()
		self.inTDSysLogger = False if self.inTDAppLogger else self.isTDSysLogger()
		self.hasParentLogger = self.ownerComp.par.Parentlogger.eval() != None
		self.parentLogger = self.ownerComp.par.Parentlogger.eval().Logger if self.ownerComp.par.Parentlogger.eval() and self.ownerComp.par.Parentlogger.eval() != self.ownerComp else None
		self.propagate = self.ownerComp.par.Propagate.eval()
		self.isLoggingToTextport = self.ownerComp.par.Logtotextport.eval()
		self.isLoggingToStatusbar = self.ownerComp.par.Logtostatusbar.eval()
		self.isLoggingToFile = self.ownerComp.par.Logtofile.eval()
		self.isLoggingToCKServer = self.ownerComp.par.Logtockserver.eval() if hasattr(self.ownerComp.par, 'Logtockserver') else False
		
		self.logLevels = logging.getLevelNamesMapping()

		if self.isLoggingEnvVarPassed and self.inTDSysLogger: 
			self.ownerComp.par.Loglevel = os.environ['TOUCH_SYS_LOG_LEVEL']

		self.LogLevel = self.ownerComp.par.Loglevel.eval()

		self.LogFolder = self.setLogFolder()
		self.IncludePID = not self.ownerComp.par.Addpidtofilename.eval()
		self.LogFileName = ''

		self.Origin = self.ownerComp.par.Origin.eval()

		loggerNamePar = self.ownerComp.par.Loggername.eval()
		self.LoggerName = loggerNamePar if loggerNamePar != '' else self.Origin.name



		self.Logger = self.createLogger('TDAppLogger') if self.inTDAppLogger else self.createLogger(self.LoggerName, parent=self.parentLogger) if self.Active else None
		
		self.LogsQueue = []
		self.postInit()

	def postInit(self):
		"""
		Called after extension initialization, 
		will call initLogger which is the main
		initialization method.
		"""
		
		if self.Active:
			if self.ownerComp.par.Loggername.eval() == '':
				self.ownerComp.par.Loggername = self.ownerComp.par.Origin.eval().name if self.ownerComp.par.Origin.eval() else parent().name
				self.LogsQueue.append((self.Warning, f'No name was provided for logger, name was set to {self.ownerComp.par.Loggername.eval()}.'))

			if self.ownerComp.par.Logfolder.eval() == '':
				self.ownerComp.par.Logfolder = pathlib.Path(project.folder) / 'TDLogs'
				self.LogsQueue.append((self.Warning, f'No folder was provided for logger, folder was set to {self.ownerComp.par.Logfolder.eval()}.'))

			self.initLogger()
			self.dequeueLogs()

	def initLogger(self):
		"""
		Initialize the logger based on the current configuration of the Logger COMP parameters.

		Set file name, create directory if required... etc.

		This will also check if the Logger should be made unique and protected if it is one of the TD loggers.

		It also creates the handler if required, 
		whether the created logger is parented or not and should propagate its messages.
		"""

		if not self.Logger:
			self.Logger = self.createLogger('TDAppLogger') if self.inTDAppLogger else self.createLogger(self.LoggerName, parent=self.parentLogger)

		self.Logger.setLevel(self.LogLevel)
		loggerName = self.Logger.name
		parentName = self.Logger.parent.name
		self.propagate = self.ownerComp.par.Propagate.eval()
		self.Logger.propagate = self.propagate

		if self.Logger.parent:
			if parentName == 'root':
				self.Info(f'The logger {loggerName} is a root logger.')
			else:
				self.Info(f'The logger {loggerName} was setup with a parent {parentName}. {loggerName} will inherit from parent.')
		
		if self.isLoggingToTextport:				
			self.initStreamHandler()
			
			if not self.getHandlerByType(self.Logger, logging.StreamHandler):
				self.createStreamHandler()

		if self.isLoggingToFile:
			self.initFileHandler()
			
			if not self.getHandlerByType(self.Logger, TimedRotatingFileHandler):
				self.createFileHandler()
		
		self.setPathToLogFile()

		return
	
	def createLogger(self, loggerName:str, parent:logging.Logger=None) -> logging.Logger:
		"""
		Create a new logging.Logger object and set it as self.Logger.
		This is the actual logging library Logger from this Logger COMP.

		When a parent is passed, 
		the new logger will use the dot notation to be parented to the parent.
		
		Args:
			loggerName (str): The name to give to the new logger object.
			parent (logging.Logger, optional): A logger to be used as parent. Defaults to None.

		Returns:
			logging.Logger: The newly created logger object.
		"""
		if parent:
			self.Logger = logging.getLogger(f'{parent.name}.{loggerName}')
		
		else:
			self.Logger = logging.getLogger(loggerName)

		return self.Logger
	
	def deleteLogger(self, loggerName:str):
		"""
		Clear the current logger as well as all related objects
		such as the handler, formatter, filter... etc.

		Args:
			loggerName (str): The name of the logger to delete.
		"""
		logger = logging.getLogger(loggerName)

		for handler in logger.handlers:
			logger.removeHandler(handler)

		logger.setLevel(logging.NOTSET)

		for filter in logger.filters:
			logger.removeFilter(filter)

		logger.propagate = False
		
		self.Logger = None

		return

	def initFileHandler(self):
		"""
		Initialize all required objects for the File handler to be created.
		This includes setting the file name, creating the log folder if necessary.

		It attempts to find an existing handler based on the log file name, if any already exists.
		"""
		if not self.LogFileName:
			self.setLogFileName()
			
		if self.Active and self.Logger and self.LogFileName:
			for handler in self.Logger.handlers:
				if handler.name == self.LogFileName:
					return

		if not self.LogFolder:
			self.setLogFolder()
		
		self.createLogFolder(self.LogFolder)
		
		return
	
	def createFileHandler(self):
		"""
		Create a new Timed Rotating file handler with the valid file path.

		This also set the formatter as well as add the created handler to the Logger.
		"""
		if self.Logger:
			myFileHandler = TimedRotatingFileHandler(
				self.getLogFilePath(),
				when='midnight',
				backupCount=self.ownerComp.par.Filerotation.eval(),
				encoding='utf8')
			myFileHandler.suffix = '%Y%m%d-%H%M%S'
			fileFormatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
			myFileHandler.setFormatter(fileFormatter)
			self.Logger.addHandler(myFileHandler)
		
		return
	
	def deleteFileHandler(self):
		"""
		Remove the current Handler from the Logger.
		"""
		self.deleteHandlerByType(self.Logger, handlerType=TimedRotatingFileHandler)
		return

	def initStreamHandler(self):
		return

	def createStreamHandler(self):
		"""
		Create a new stream handler.

		This also set the formatter as well as add the created handler to the Logger.
		"""
		if self.Logger:
			myStreamHandler = logging.StreamHandler()
			myStreamHandler.suffix = '%Y%m%d-%H%M%S'
			streamFormatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
			myStreamHandler.setFormatter(streamFormatter)
			self.Logger.addHandler(myStreamHandler)

	def deleteStreamHanlder(self):
		"""
		Remove the current Handler from the Logger.
		"""
		self.deleteHandlerByType(self.Logger, handlerType=logging.StreamHandler)
		return

	def deleteHandlerByName(self, logger:logging.Logger, handlerName:str):
		"""
		Delete handler when a handler with a matching handler name is 
		found on the logger.

		Args:
			logger (logging.Logger): The logger object on which to search the handler of the given name.
			handlerName (str): The name of the handler to remove.
		"""
		if self.Logger:
			for handler in self.Logger.handlers:
				if handler.name == handlerName:
					self.Logger.removeHandler(handler)

		return

	def deleteHandlerByType(self, logger:logging.Logger, handlerType:logging.Handler):
		"""
		Delete handler(s) when any handler with a matching type is 
		found on the logger.

		Args:
			logger (logging.Logger): The logger object on which to search for a handler of a matching type.
			handlerType (logging.Handler): Search for handlers of the given handler type.
		"""
		if self.Logger:
			for handler in self.Logger.handlers:
				if type(handler) is handlerType:
					self.Logger.removeHandler(handler)

		return

	def ClearHandlers(self):
		"""
		In the case that a Logger get reinitialized and an handler get duplicated
		use this method to clear the handlers.

		A new handler should be created after calling createFileHandler or similar.
		"""
		if self.Logger:
			for handler in self.Logger.handlers:
				self.Logger.removeHandler(handler)

	#region Main Logging Methods
	def Log(self, *args, level: str, withInfos: bool = True, **logItemDict: dict) -> None:
		"""
		This is the main method called from the overrides for Info, Debug, Error, etc.

		It is going through additional checks before calling the underlying methods to
		log messages to file, textport, or statusbar.

		All those additional method calls are subject to the current parameters setup of
		the logger COMP.

		When a Callback DAT is added, the callback onMessageLogged() will be called,
		passing the logItemDict to the user.

		Args:
			message (str): The required message to be added to the LogItem. A message can be an empty string.
			level (str): The required LogLevel, such as ERROR, WARNING, INFO, etc.
			withInfos (bool): Include additional informations in log message from the stack trace. Defaults to True.
			**logItemDict (dict): Additional keywords can be used to override the default data
			such as `source`, `absFrame`, `frame`
		"""
		if self.Active:
			reprMessage = [repr(arg) if not isinstance(arg, str) else arg for arg in args]
			logItemDict['message'] = ' - '.join(reprMessage)
			logItemDict['level'] = level
			logItemDict['source'] =""
			logItemDict['stackInfos'] = logItemDict.get('stackInfos', self.getStackInfos() if withInfos else None)
			logItemDict['absFrame'] = logItemDict.get('absFrame', absTime.frame)
			logItemDict['frame'] = logItemDict.get('frame', self.ownerComp.time.frame)
			logItemDict['completeInfos'] = logItemDict.get('completeInfos', '')
			
			logLevelSetting = self.LogLevel

			logItemDict['source'] = f"PID:{str(os.getpid())} - {logItemDict['source']}" if self.IncludePID else logItemDict['source']
			if logItemDict['stackInfos']:
				logItemDict['completeInfos'] += f" (DAT:{logItemDict['stackInfos']['fileName']}, fn:{logItemDict['stackInfos']['fn']}, ln:{logItemDict['stackInfos']['ln']}, absFrame: {logItemDict['absFrame']}, frame: {logItemDict['frame']})"

			else:
				logItemDict['completeInfos'] += f" (absFrame: {logItemDict['absFrame']}, frame: {logItemDict['frame']})"

			if self.LogsQueue:
				self.dequeueLogs()

			self.logWithHandlers(logItemDict)
			
			if self.isLoggingToStatusbar:
				if self.logLevels.get(logItemDict['level'], 0) >= self.logLevels.get(logLevelSetting, 0):
					self.logToStatus(logItemDict)
			
			if self.isLoggingToCKServer:
				if self.logLevels.get(logItemDict['level'], 0) >= self.logLevels.get(logLevelSetting, 0):
					self.logToCKServer(logItemDict)

			"""
			onMessageLogged()
			"""
			if hasattr(self.ownerComp.ext, 'CallbacksExt'):
				info = {
					'logItemDict': logItemDict
				}
				self.ownerComp.ext.CallbacksExt.DoCallback('onMessageLogged', info)

	def Info(self, *args, withInfos: bool = True) -> None:
		"""Log an Info message.

		Args:
			message (str): The required message to be added to the LogItem. A message can be an empty string.
		"""
		self.Log(*args, level='INFO', withInfos=withInfos)
		return
	
	def Debug(self, *args, withInfos: bool = True) -> None:
		"""Log a Debug message.

		Args:
			message (str): The required message to be added to the LogItem. A message can be an empty string.
		"""
		self.Log(*args, level='DEBUG', withInfos=withInfos)
		return

	def Warning(self, *args, withInfos: bool = True) -> None:
		"""Log a Warning message.

		Args:
			message (str): The required message to be added to the LogItem. A message can be an empty string.
		"""
		self.Log(*args, level='WARNING', withInfos=withInfos)
		return

	def Error(self, *args, withInfos: bool = True) -> None:
		"""Log an Error message.

		Args:
			message (str): The required message to be added to the LogItem. A message can be an empty string.
		"""
		self.Log(*args, level='ERROR', withInfos=withInfos)
		return

	def Critical(self, *args, withInfos: bool = True) -> None:
		"""Log a Critical message.

		Args:
			message (str): The required message to be added to the LogItem. A message can be an empty string.
		"""
		self.Log(*args, level='CRITICAL', withInfos=withInfos)
		return

	def logWithHandlers(self, logItemDict: dict) -> None:
		"""
		Using the logItemDict prepared in the Log method,
		prepare a log message to pass
		to the matching logging library method to log a message at the
		expected log level. i.e. if the level is INFO, logger.info(message) will be called.

		The log message will be preceeded by additional informations specified by the logger.Formatter.

		Args:
			logItemDict (dict): A dictionnary holding all the required informations for the formatting of the log message.
		"""

		logMsg = f"{logItemDict['source']} - {logItemDict['message']}"
		logMsg += logItemDict['completeInfos']

		level = logItemDict['level']
		logFn = level if isinstance(level, str) else logging.getLevelName(level) if isinstance(level, int) else 'info'

		try:
			getattr(self.Logger, logFn.lower())(logMsg)
		except Exception as err:
			self.LogsQueue.append((self.Error, f'An error occured while trying to log with handlers. {err}.'))
			self.LogsQueue.append((getattr(self, logFn), logMsg))
		
		return

	def logToStatus(self, logItemDict: dict) -> None:
		""" 
		Using the logItemDict prepared in the Log method,
		pass the message to the statusbar using ui.status.

		Args:
			logItemDict (dict): A dictionnary holding all the required informations for the formatting of the log message.
		"""
		ui.status = f"{logItemDict['level']} - {logItemDict['source']} - {logItemDict['message']}{logItemDict['completeInfos']}"
		return

	def logToCKServer(self, logItemDict: dict) -> None:
		"""
		Using the logItemDict prepared in the Log method,
		send the log message to the remote CKServer API.

		Args:
			logItemDict (dict): A dictionnary holding all the required informations for the log message.
		"""
		# Prevent infinite loop if error occurs during CKServer logging
		if hasattr(self, '_ckserver_error_logged') and self._ckserver_error_logged:
			return
			
		try:
			# Get device_id and user_id from StateMachine if available
			device_id = op.StateMachine.ClientId if hasattr(op, 'StateMachine') and hasattr(op.StateMachine, 'ClientId') else f"{project.name.split('.')[0]}"
			user_id = op.StateMachine.Payload if hasattr(op, 'StateMachine') and hasattr(op.StateMachine, 'Payload') else ""
			
			# Format log message: [LEVEL] logger_name - message (file:line)
			log_parts = [f"[{logItemDict['level']}]", self.LoggerName]
			
			if logItemDict['source']:
				log_parts.append(logItemDict['source'])
			
			log_parts.append(logItemDict['message'])
			
			# Add stack info if available
			if logItemDict['stackInfos']:
				stack_info = f"({logItemDict['stackInfos']['fileName']}:{logItemDict['stackInfos']['ln']})"
				log_parts.append(stack_info)
			
			log_message = " - ".join(log_parts)
			
			# Map TD log level to lowercase
			level = logItemDict['level'].lower()
			
			# Send to CKServer with specific error handling
			try:
				result = client.log_append(
					device_id=device_id,
					msg=log_message,
					user_id=user_id,
					level=level
				)
				
				if not result.get('ok'):
					self._ckserver_error_logged = True
					print(f"CKServer logging failed: {result.get('error', result.get('message', 'Unknown error'))}")
					self._ckserver_error_logged = False
					
			except requests.exceptions.HTTPError as http_err:
				self._ckserver_error_logged = True
				#print(f"CKServer HTTP error: {http_err.response.status_code} - {http_err.response.reason}")
				try:
					error_data = http_err.response.json()
					pass
				except:
					pass
				self._ckserver_error_logged = False
				
			except requests.exceptions.RequestException as req_err:
				self._ckserver_error_logged = True
				print(f"CKServer request error: {req_err}")
				self._ckserver_error_logged = False
				
		except Exception as err:
			# Catch-all for unexpected errors
			self._ckserver_error_logged = True
			print(f"Unexpected error in CKServer logging: {err}")
			self._ckserver_error_logged = False
		
		return

	def getStackInfos(self, stackOffset:int=2) -> dict:
		"""
		A method going back up the stack frames to get informations about the original calling method.

		This is using the inspect library.

		Args:
			stackOffset (int, optional): From this method, 
			how many frames do we have to offset to get to the original calling method. Defaults to 2.

		Returns:
			dict: A dictionnary with all the required informations regarding the original caller origin.
		"""
		stackInfos = None
		
		stack = inspect.stack()
		
		if len(stack) > 1 + stackOffset:
			frame = stack[1 + stackOffset][0]
			info = inspect.getframeinfo(frame)
			stackInfos = {
				'fileName':info.filename,
				'fn': info.function,
				'ln': info.lineno
			}

		del(stack)
		return stackInfos
	
	#endregion

	#region Utilities
	"""
	Main Logging Methods #END		
	"""

	def setLogFolder(self) -> str:
		"""
		Set self.LogFolder. 
		Set to project.folder/TDLogs if no Logfolder is set as the parameter.

		Returns:
			str: self.LogFolder after generating its new value.
		"""
		self.LogFolder = self.ownerComp.par.Logfolder.eval() if self.ownerComp.par.Logfolder.eval() else project.folder + '/TDLogs'
		return self.LogFolder

	def setLogFileName(self) -> str:
		"""
		Generate the baseName of the log file based
		on the project name, the current process PID, and the logger name.

		Set self.LogFileName.

		Returns:
			str: self.LogFileName after generating its new value.
		"""
		self.LogFileName = ''
		self.LogFileName += project.name.split('.')[0]
		self.LogFileName += '_'
		
		if not self.IncludePID:
			self.LogFileName += str(os.getpid()) + '_' + self.LoggerName
		else:
			self.LogFileName += self.LoggerName

		return self.LogFileName

	def setPathToLogFile(self):
		"""
		This method set the path to the log file, based on various parameters.

		When a parameter of the current Logger COMP gets changed, it can have an impact 
		on the current log file path.

		When the current logger doesn't have file logging turned on, it doesn't
		mean that the log messages don't end up in a file. The messages could be passed
		to a parent logger, and this method attempt to find the path to a parent logger
		file handler.
		"""
		if self.Logger and self.Logger.hasHandlers and self.isLoggingToFile:
			fileHandlers = self.getHandlerByType(self.Logger, TimedRotatingFileHandler)
			nbFileHandlers = len(fileHandlers)

			if nbFileHandlers > 1:
				self.Warning(f'{self.Logger.name} has more than 1 file handler, this could cause unexpected behaviors.')
			elif not nbFileHandlers:
				self.Warning(f'{self.Logger.name} has no file handler.')
				return

			myFileHandler = fileHandlers[0]
			if myFileHandler:
				self.ownerComp.par.Pathtologfile = myFileHandler.baseFilename

		elif self.Logger:
			parentHandler = self.getParentHandler(self.Logger, TimedRotatingFileHandler)
			if parentHandler:		
				self.ownerComp.par.Pathtologfile = parentHandler.baseFilename
		
		else:
			self.ownerComp.par.Pathtologfile = ''

		return

	def getParentHandler(self, logger: logging.Logger, handlerType:logging.Handler=None) -> logging.Handler|None:
		"""
		Given a Logger object, attempts to find if they are any parent logger
		with a valid and active handler.

		Args:
			logger (logging.Logger): The logger with a potential parent.

		Returns:
			Optional[TimedRotatingFileHandler]: Returns a potential file handler.
		"""
		if logger and logger.parent:
			parentLogger = logger.parent

			for handler in parentLogger.handlers:
				if type(handler) is handlerType:
					return handler

			self.getParentHandler(parentLogger)
		
		return None
	
	def createLogFolder(self, path: str) -> None:
		"""
		Given a folder path as a string,
		verify if the folder exists, if not create the tree to the given path.

		Args:
			path (str): The path to the folder to create.
		"""
		if not os.path.exists(path):
			os.makedirs(path)
		
		return

	def getLogFilePath(self) -> str:
		"""
		Use the current values of LogFolder and LogFileName to get the full path,
		as a string, to the .log file.

		Returns:
			str: The path to the log file.
		"""
		return f'{self.LogFolder}/{self.LogFileName}.log'

	def isTDSysLogger(self) -> bool:
		"""
		A method used to confirm whether the current Logger COMP instance is the TDSysLogger.

		Returns:
			bool: Whether or not the current Logger COMP met all the requirements to be a TDSysLogger.
		"""		
		cloneMasterCOMP = self.ownerComp.par.clone.eval()

		isCloneOfTDToxLogger = True if cloneMasterCOMP and cloneMasterCOMP.parent() == op.TDTox and cloneMasterCOMP.name == 'logger' else False
		isOriginSys = True if self.ownerComp.par.Origin.eval() == op('/sys') else False
		isNamedTDSys = True if self.ownerComp.par.Loggername.eval() == 'TDSysLogger' else False
		
		isTDSysLogger = True if isCloneOfTDToxLogger and isOriginSys and isNamedTDSys else False
		
		return isTDSysLogger
	
	def isTDAppLogger(self) -> bool:
		"""
		A method used to confirm whether the current Logger COMP instance is the TDAppLogger.

		Returns:
			bool: Whether or not the current Logger COMP met all the requirements to be a TDAppLogger.
		"""
		cloneMasterCOMP = self.ownerComp.par.clone.eval()

		isCloneOfTDToxLogger = True if cloneMasterCOMP and cloneMasterCOMP.parent() == op.TDTox and cloneMasterCOMP.name == 'logger' else False
		isOriginSys = True if self.ownerComp.par.Origin.eval() == op('/') else False
		isNamedTDApp = True if self.ownerComp.par.Loggername.eval() == 'TDAppLogger' else False
		
		isTDAppLogger = True if isCloneOfTDToxLogger and isOriginSys and isNamedTDApp else False
		
		return isTDAppLogger

	def dequeueLogs(self):
		"""
		Process logs that were queued.
		"""
		for log in self.LogsQueue:
			log[0](log[1])
			self.LogsQueue.remove(log)

	def getHandlerByName(self, logger:logging.Logger, handlerName:str) -> logging.Handler|None:
		"""
		Get handler when a handler with a matching handler name is 
		found on the logger.

		Args:
			logger (logging.Logger): The logger object on which to search the handler of the given name.
			handlerName (str): The name of the handler to return, if found.	

		Returns:
			logging.Handler|None: Return a Handler when found, or None otherwise.
		"""
		for handler in logger.handlers:
			if handler.get_name() == handlerName:
				return handler
		
		return None

	def getHandlerByType(self, logger:logging.Logger, handlerType:logging.Handler) -> list[logging.Handler]:
		"""
		Get any handler found where a matching handler type is 
		found on the logger.

		Args:
			logger (logging.Logger): The logger object on which to search the handler(s) of the matching type.
			handlerType (logging.Handler): The type of the handler(s) to search and match.

		Returns:
			list[logging.Handler]: A, possibly empty, list of handlers.
		"""
		handlers = []
		for handler in logger.handlers:
			if type(handler) is handlerType:
				handlers.append(handler)		
		
		return handlers

	#endregion

	#region Parameters Callbacks

	"""
	Parameter changes can have an important impact on the current logger or any of its handlers.

	When the following parameter are changing:
		Active
			init or delete logger
		Parent Logger
			init or delete logger
			set path to log file
		Propagate change
			delete and init new file handler
			set path to log file
		Origin change (light impact)
			LogItems will get the update
		Log level change (light impact)
			set the logger level
		Log app errors (light impact)
		Log to textport (light impact)
		Log to status bar (light impact)
		Logger name change
			init or delete logger
			set path to log file
		Log to file
			init or delete file handler
			set path to log file
		Log folder
			init or delete file handler
			set path to log file				
		Add PID to file name
			init or delete file handler
			set path to log file
	"""

	def OnActiveChange(self, par, prev):
		self.Active = par.eval()
		if self.Active:
			self.initLogger()

		elif not self.Active and prev:
			self.deleteLogger(self.Logger.name)

		return

	def OnParentloggerChange(self, par, prev):
		if self.Logger:
			self.deleteLogger(self.Logger.name)
			
		if self.Active:
			self.initLogger()

		self.setPathToLogFile()
		return

	def OnPropagateChange(self, par, prev):
		self.propagate = par.eval()

		if self.Logger:
			self.Logger.propagate = self.propagate
		
		if self.propagate != prev:
			self.setPathToLogFile()
		return

	def OnOriginChange(self, par, prev):
		self.Origin = par.eval()
		return

	def OnLoglevelChange(self, par, prev):
		self.LogLevel = par.eval()
		if self.Logger:
			self.Logger.setLevel(self.LogLevel)
		
		return
	
	def OnLogapperrorsChange(self, par, prev):
		self.Info(f'Log app errors was changed from {prev} to {par.eval()}')
		return
	
	def OnLoggernameChange(self, par, prev):
		self.Info(f'Logger name will be changed from {self.LoggerName} to {par.eval()}')
		
		if self.Logger:
			self.deleteLogger(self.LoggerName)
			
		self.LoggerName = par.eval()
		
		self.setLogFileName()

		if self.Active:
			self.initLogger()
		
		return

	def OnLogtotextportChange(self, par, prev):
		self.isLoggingToTextport = par.eval()

		if not self.Logger:
			return

		if self.isLoggingToTextport:
			if self.Logger.hasHandlers and self.getHandlerByType(self.Logger, logging.StreamHandler):
				self.deleteStreamHanlder()			

			self.initStreamHandler()
			self.createStreamHandler()
		
		elif not self.isLoggingToTextport and prev:
			self.deleteStreamHanlder()


	def OnLogtofileChange(self, par, prev):
		self.isLoggingToFile = par.eval()
		
		if not self.Logger:
			self.setPathToLogFile()
			return

		if self.isLoggingToFile:
			if self.Logger.hasHandlers and self.getHandlerByType(self.Logger, TimedRotatingFileHandler):
				self.deleteFileHandler()
			
			self.initFileHandler()
			self.createFileHandler()

		elif not self.isLoggingToFile and prev:
			self.deleteFileHandler()

		self.setPathToLogFile()
		return

	def OnLogtockserverChange(self, par, prev):
		"""Handle CKServer logging toggle."""
		self.isLoggingToCKServer = par.eval()
		
		if self.isLoggingToCKServer:
			self.Info('CKServer remote logging enabled')
			# Test connection
			try:
				health = client.health()
				
				if isinstance(health, dict) and health.get('ok'):
					actions = health.get('actions', [])
					self.Info(f"CKServer connection successful (PHP {health.get('php', 'unknown')}, {len(actions)} actions available)")
				else:
					error_msg = health.get('error') or health.get('message') or 'Health check returned ok=False'
					self.Warning(f"CKServer health check failed: {error_msg}")
			except Exception as err:
				self.Error(f"CKServer connection test failed: {err}")
		else:
			self.Info('CKServer remote logging disabled')
		
		return

	def OnLogfolderChange(self, par, prev):
		if par.eval() == prev:
			return
		
		if self.isLoggingToFile:
			return

		if self.Logger and self.Logger.hasHandlers and self.getHandlerByType(self.Logger, TimedRotatingFileHandler):
			self.deleteFileHandler()

		self.setLogFolder()

		self.createLogFolder(self.LogFolder)

		self.createFileHandler()
		
		self.setPathToLogFile()

		return
		
	def OnOpenlogfolderPulse(self, par):
		if self.ownerComp.par.Pathtologfile.eval() == '':
			folderPath = self.ownerComp.par.Logfolder.eval()
		else:
			folderPath = self.getHandlerFolder(self.ownerComp.par.Pathtologfile.eval())
		
		system = platform.system()
		folderPath = pathlib.Path(folderPath)
		if system == "Windows":
			subprocess.Popen(["explorer", folderPath])
		elif system == "Darwin":
			subprocess.Popen(["open", folderPath])
	
	def OnAddpidtofilenameChange(self, par, prev):
		self.IncludePID = not par.eval()
		prevFileName = str(self.LogFileName)
		self.setLogFileName()

		self.Info(f'Logger file name will be changed from {prevFileName} to {self.LogFileName}')
		
		if self.Logger.hasHandlers and self.getHandlerByType(self.Logger, TimedRotatingFileHandler):
			self.deleteFileHandler()
		
		self.initFileHandler()	
		self.createFileHandler()
		self.setPathToLogFile()
		return	
	
	def getHandlerFolder(self, pathToFile: str):
		"""
		Given a path to a log file, find the folder in which the file is stored.

		Args:
			pathToFile (str): A path to a log file.

		Returns:
			str: A path to a folder.
		"""
		pathToFile = pathlib.Path(pathToFile)
		folder = app.configFolder
		
		if pathToFile.exists and pathToFile.is_file:
			folder = pathToFile.parent
			
		return folder

	def OnOpenlogfilePulse(self, par):
		system = platform.system()
		pathToFile = pathlib.Path(self.ownerComp.par.Pathtologfile.eval())
		
		if pathToFile.exists and pathToFile.is_file:
			if system == "Windows":
				os.startfile(pathToFile)
			
			elif system == "Darwin":
				subprocess.Popen(["open", str(pathToFile)])

	def OnFilerotationChange(self, par, prev):
		if self.Logger.hasHandlers and self.getHandlerByType(self.Logger, TimedRotatingFileHandler):
			self.deleteFileHandler()
			self.createFileHandler()

		return

	def OnOpenparametersdialogPulse(self, par):
		self.ownerComp.openParameters()

	def OnCreatecallbackdatPulse(self, par):
		"""
		When the parameter is pulsed, create a callback DAT underneath the owner COMP.
		"""
		callbackName = parent().name+'_callbacks'

		callbackDAT = None

		if self.ownerComp.par.Callbackdat.eval():
			callbackDAT = self.ownerComp.par.Callbackdat.eval()

		if self.ownerComp.parent().op(callbackName):
			callbackDAT = self.ownerComp.parent().op(callbackName)

		if callbackDAT:
			dat = callbackDAT
		else:
			dat = self.ownerComp.parent().create(textDAT, callbackName)

		dat.nodeY = self.ownerComp.nodeY - 125
		dat.nodeX = self.ownerComp.nodeX
		dat.dock = self.ownerComp
		
		if not callbackDAT:
			# preventing current callback text to be cleared
			dat.text = self.ownerComp.op('callbacksTemplate').text
		
		dat.viewer = True
		dat.par.language = 'Python'
		dat.par.extension = 7
		self.ownerComp.par.Callbackdat = dat.name
		return

	def aboutPageUpdate(self, parPage='About'):
		"""
		Update the About page parameters for clones so tha they reflect the .tox clone master actual values
		although those parameters are read only.

		Args:
			parPage (str, optional): The page on which the parameters should be present. Defaults to 'About'.
		"""
		parsToReset = ['Version', 'Toxsavebuild']

		for parToReset in parsToReset:
			par_ = getattr(self.ownerComp.par, parToReset) if hasattr(self.ownerComp.par, parToReset) else None
			if par_ and par_.page == parPage:
				self.updateReadOnlyParToDefault(par_)

	def updateReadOnlyParToDefault(self, par):
		"""
		Check if the parameter is currently set ot its default,
		if not, the parameter is set to default, even if the parameter is currently in read only mode.

		Args:
			par (Par): The parameter to reset.
		"""
		if par.default != par.eval():
			par.val = par.default

	#endregion
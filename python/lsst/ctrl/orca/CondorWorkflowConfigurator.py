# 
# LSST Data Management System
# Copyright 2008, 2009, 2010 LSST Corporation.
# 
# This product includes software developed by the
# LSST Project (http://www.lsst.org/).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the LSST License Statement and 
# the GNU General Public License along with this program.  If not, 
# see <http://www.lsstcorp.org/LegalNotices/>.
#

import stat, sys, os, os.path, shutil, sets, stat, socket
from sets import Set
import getpass
import lsst.ctrl.orca as orca
import lsst.pex.config as pexConfig

from lsst.ctrl.orca.Directories import Directories
from lsst.pex.logging import Log

from lsst.ctrl.orca.EnvString import EnvString
#from lsst.ctrl.orca.ConfigUtils import ConfigUtils
from lsst.ctrl.orca.WorkflowConfigurator import WorkflowConfigurator
from lsst.ctrl.orca.CondorWorkflowLauncher import CondorWorkflowLauncher
from lsst.ctrl.orca.config.PlatformConfig import PlatformConfig
from lsst.ctrl.orca.TemplateWriter import TemplateWriter
from lsst.ctrl.orca.FileWaiter import FileWaiter

##
#
# CondorWorkflowConfigurator 
#
class CondorWorkflowConfigurator(WorkflowConfigurator):
    def __init__(self, runid, repository, prodConfig, wfConfig, wfName, logger):
        self.logger = logger
        self.logger.log(Log.DEBUG, "CondorWorkflowConfigurator:__init__")

        self.runid = runid
        self.repository = repository
        self.prodConfig = prodConfig
        self.wfConfig = wfConfig
        self.wfName = wfName

        self.wfVerbosity = None

        self.dirs = None
        self.directories = None
        self.nodes = None
        self.numNodes = None
        self.logFileNames = []
        self.pipelineNames = []

        self.directoryList = {}
        self.initialWorkDir = None
        self.firstRemoteWorkDir = None
        self.defaultRoot = wfConfig.platform.dir.defaultRoot
        
    ##
    # @brief Setup as much as possible in preparation to execute the workflow
    #            and return a WorkflowLauncher object that will launch the
    #            configured workflow.
    # @param provSetup
    # @param wfVerbosity
    #
    def configure(self, provSetup, wfVerbosity):
        self.wfVerbosity = wfVerbosity
        self._configureDatabases(provSetup)
        return self._configureSpecialized(provSetup, self.wfConfig)

    ##
    # @brief Setup as much as possible in preparation to execute the workflow
    #            and return a WorkflowLauncher object that will launch the
    #            configured workflow.
    # @param provSetup
    # @param wfConfig
    #
    def _configureSpecialized(self, provSetup, wfConfig):
        self.logger.log(Log.DEBUG, "CondorWorkflowConfigurator:configure")

        localConfig = wfConfig.configuration["condor"]
        self.localScratch = localConfig.condorData.localScratch

        platformConfig = wfConfig.platform
        taskConfigs = wfConfig.task


        self.localStagingDir = os.path.join(self.localScratch, self.runid)
        os.makedirs(self.localStagingDir)

        # write the glidein file
        startDir = os.getcwd()
        os.chdir(self.localStagingDir)

        if localConfig.glidein.template.inputFile is not None:
            self.writeGlideinFile(localConfig.glidein)
        else:
            self.logger.log(Log.DEBUG, "CondorWorkflowConfigurator: not writing glidein file")
        os.chdir(startDir)

        # TODO - fix this loop for multiple condor submits; still working
        # out what this might mean.
        for taskName in taskConfigs:
            task = taskConfigs[taskName]
            self.scriptDir = task.scriptDir
            
            # save initial directory we were called from so we can get back
            # to it
            startDir = os.getcwd()

            # switch to staging directory
            os.chdir(self.localStagingDir)

            # switch to tasks directory in staging directory
            taskOutputDir = os.path.join(self.localStagingDir, task.scriptDir)
            os.makedirs(taskOutputDir)
            os.chdir(taskOutputDir)

            # generate pre job 
            preJobScript = EnvString.resolve(task.preJob.script.outputFile)
            preJobScriptInputFile = EnvString.resolve(task.preJob.script.inputFile)
            keywords = task.preJob.script.keywords
            self.writeJobScript(preJobScript, preJobScriptInputFile, keywords)

            preJobCondorOutputFile = EnvString.resolve(task.preJob.condor.outputFile)
            preJobCondorInputFile = EnvString.resolve(task.preJob.condor.inputFile)
            keywords = task.preJob.condor.keywords
            self.writeJobScript(preJobCondorOutputFile, preJobCondorInputFile, keywords, preJobScript)
            
        
            # generate post job
            postJobScript = EnvString.resolve(task.postJob.script.outputFile)
            postJobScriptInputFile = EnvString.resolve(task.postJob.script.inputFile)
            keywords = task.postJob.script.keywords
            self.writeJobScript(postJobScript, postJobScriptInputFile, keywords)

            postJobCondorOutputFile = EnvString.resolve(task.postJob.condor.outputFile)
            postJobCondorInputFile = EnvString.resolve(task.postJob.condor.inputFile)
            keywords = task.postJob.condor.keywords
            self.writeJobScript(postJobCondorOutputFile, postJobCondorInputFile, keywords, postJobScript)

            # generate worker job
            workerJobScript = EnvString.resolve(task.workerJob.script.outputFile)
            workerJobScriptInputFile = EnvString.resolve(task.workerJob.script.inputFile)
            keywords = task.workerJob.script.keywords
            self.writeJobScript(workerJobScript, workerJobScriptInputFile, keywords)

            workerJobCondorOutputFile = EnvString.resolve(task.workerJob.condor.outputFile)
            workerJobCondorInputFile = EnvString.resolve(task.workerJob.condor.inputFile)
            keywords = task.workerJob.condor.keywords
            self.writeJobScript(workerJobCondorOutputFile, workerJobCondorInputFile, keywords, workerJobScript)

            # switch to staging directory
            os.chdir(self.localStagingDir)

            # generate pre script

            if task.preScript.script.outputFile is not None:
                preScriptOutputFile = EnvString.resolve(task.preScript.script.outputFile)
                preScriptInputFile = EnvString.resolve(task.preScript.script.inputFile)
                keywords = task.preScript.script.keywords
                self.writePreScript(preScriptOutputFile, preScriptInputFile, keywords)
                os.chmod(task.preScript.outputFile, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
            
            # generate dag
            dagGenerator = EnvString.resolve(task.dagGenerator.script)
            dagGeneratorInput = EnvString.resolve(task.dagGenerator.input)
            dagCreatorCmd = [dagGenerator, "-s", dagGeneratorInput, "-w", task.scriptDir, "-t", task.workerJob.condor.outputFile, "-r", self.runid, "--idsPerJob", str(task.dagGenerator.idsPerJob)]
            if task.preScript.script.outputFile is not None:
                dagCreatorCmd.append("-p")
                dagCreatorCmd.append(task.preScript.script.outputFile)
            pid = os.fork()
            if not pid:
                # turn off all output from this command
                sys.stdin.close()
                sys.stdout.close()
                sys.stderr.close()
                os.close(0)
                os.close(1)
                os.close(2)
                os.execvp(dagCreatorCmd[0], dagCreatorCmd)
            os.wait()[0]

            # create dag logs directories
            fileObj = open(dagGeneratorInput,'r')
            visitSet = set()
            count = 0
            # this info from gd:
            # Searching for a space detects 
            # extended input like :  visit=887136081 raft=2,2 sensor=0,1
            # No space is something simple like a skytile id  
            for aline in fileObj:
                count += 1
                #myData = aline.rstrip()
                #if " " in myData:
                #    myList = myData.split(' ')
                #    visit = myList[0].split('=')[1]
                #else:
                #    visit = myData
                visit = str(int(count / 100))
                visitSet.add(visit)
            logDirName = os.path.join(self.localStagingDir, "logs")
            for visit in visitSet:
                dirName = os.path.join(logDirName, str(visit))
                os.makedirs(dirName)
            
            # change back to initial directory
            os.chdir(startDir)

        # create the Launcher

        #workflowLauncher = CondorWorkflowLauncher(jobs, self.initialWorkDir,  self.prodConfig, self.wfConfig, self.runid, self.pipelineNames, self.logger)
        workflowLauncher = CondorWorkflowLauncher(self.prodConfig, self.wfConfig, self.runid, self.localStagingDir, task.dagGenerator.dagName+".diamond.dag", wfConfig.monitor, self.logger)
        return workflowLauncher

    # TODO - XXX - these next two should probably be combined
    def writePreScript(self, outputFileName, template, keywords):
        pairs = {}
        for value in keywords:
            val = keywords[value]
            pairs[value] = val
        pairs["ORCA_RUNID"] = self.runid
        pairs["ORCA_DEFAULTROOT"] = self.defaultRoot
        writer = TemplateWriter()
        writer.rewrite(template, outputFileName, pairs)

    def writeJobScript(self, outputFileName, template, keywords, scriptName = None):
        pairs = {}
        for value in keywords:
            val = keywords[value]
            pairs[value] = val
        if scriptName is not None:
            pairs["ORCA_SCRIPT"] = self.scriptDir+"/"+scriptName
        pairs["ORCA_RUNID"] = self.runid
        pairs["ORCA_DEFAULTROOT"] = self.defaultRoot
        writer = TemplateWriter()
        writer.rewrite(template, outputFileName, pairs)

    def writeGlideinFile(self, glideinConfig):
        template = glideinConfig.template
        inputFile = EnvString.resolve(template.inputFile)

        # copy the keywords so we can add a couple more
        pairs = {}
        for value in template.keywords:
            val = template.keywords[value]
            pairs[value] = val
        pairs["ORCA_REMOTE_WORKDIR"] = self.defaultRoot+"/"+self.runid
        if pairs.has_key("ORCA_START_OWNER") == False:
            pairs["ORCA_START_OWNER"] = getpass.getuser()

        writer = TemplateWriter()
        writer.rewrite(inputFile, template.outputFile, pairs)
          

    def getWorkflowName(self):
        return self.wfName


    ##
    # @brief 
    #
    def deploySetup(self, provSetup, wfConfig, platformConfig, pipelineConfigGroup):
        self.logger.log(Log.DEBUG, "CondorWorkflowConfigurator:deploySetup")


    ##
    # @brief create the platform.dir directories
    #
    def createDirs(self, localStagingDir, platformDirConfig):
        self.logger.log(Log.DEBUG, "CondorWorkflowConfigurator:createDirs")


    ##
    # @brief set up this workflow's database
    #
    def setupDatabase(self):
        self.logger.log(Log.DEBUG, "CondorWorkflowConfigurator:setupDatabase")

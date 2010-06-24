import os, sys, subprocess
import lsst.ctrl.orca as orca
from lsst.pex.logging import Log
from lsst.ctrl.orca.EnvString import EnvString
from lsst.ctrl.orca.WorkflowMonitor import WorkflowMonitor
from lsst.ctrl.orca.WorkflowLauncher import WorkflowLauncher
from lsst.ctrl.orca.CondorJobs import CondorJobs
from lsst.ctrl.orca.VanillaCondorWorkflowMonitor import VanillaCondorWorkflowMonitor

class VanillaCondorWorkflowLauncher(WorkflowLauncher):
    ##
    # @brief
    #
    def __init__(self, jobs, localScratch, condorGlideinFile, prodPolicy, wfPolicy, runid, filewaiter, logger = None):
        if logger != None:
            logger.log(Log.DEBUG, "VanillaCondorWorkflowLauncher:__init__")
        self.logger = logger
        self.jobs = jobs
        self.localScratch = localScratch
        self.condorGlideinFile = condorGlideinFile
        self.prodPolicy = prodPolicy
        self.wfPolicy = wfPolicy
        self.runid = runid
        self.filewaiter = filewaiter

    ##
    # @brief perform cleanup after workflow has ended.
    #
    def cleanUp(self):
        if self.logger != None:
            self.logger.log(Log.DEBUG, "VanillaCondorWorkflowLauncher:cleanUp")

    ##
    # @brief launch this workflow
    #
    def launch(self, statusListener):
        if self.logger != None:
            self.logger.log(Log.DEBUG, "VanillaCondorWorkflowLauncher:launch")

        # Three step launch process
        # 1 - Glidein request
        # wait for glidein to complete
        # 2 - start joboffice job
        # wait for joboffice to start
        # 3 - start all other jobs.
        # wait for all other jobs to start
        # notify the user it's time to do the announceData

        condor = CondorJobs(self.logger)

        # if we've set the "skipglidein", just don't do that.
        if orca.skipglidein == False:
            curDir = os.getcwd()

            # switch to this directory to make condor happy
            os.chdir(self.localScratch)
            glideinJobNumber = condor.submitJob(self.condorGlideinFile)
            os.chdir(curDir)

            # write the glidein job file to the workflow's directory
            tempWorkDir = os.path.dirname(self.condorGlideinFile)
            tempPipelineDir = os.path.dirname(tempWorkDir)
            workflowDir = os.path.dirname(tempPipelineDir)
            glideinJobFile = os.path.join(workflowDir, "glidein.job")
            self.writeJobFile(glideinJobNumber, glideinJobFile)

            # now wait for it to show up.
            condor.waitForJobToRun(glideinJobNumber, "this might take a few minutes.")
        else:
            print "Command line request to skip condor glidein.  Skipping."

        # for now, make sure joboffice is the first job, launch and wait for it
        firstJob = True
        jobNumbers = []
        for job in self.jobs:
            if firstJob == True:
                jobNumber = condor.submitJob(job)
                jobDir = os.path.dirname(job)
                jobFileName = os.path.join(jobDir, "%s.job" % os.path.basename(jobDir))
                self.writeJobFile(jobNumber, jobFileName)
                condor.waitForJobToRun(jobNumber)
                # Wait for that first log file to show up from joboffice
                self.filewaiter.waitForFirstFile()
                firstJob = False
            else:
                jobNumber = condor.submitJob(job)
                jobDir = os.path.dirname(job)
                jobFileName = os.path.join(jobDir, "%s.job" % os.path.basename(jobDir))
                self.writeJobFile(jobNumber, jobFileName)
                jobNumbers.append(jobNumber)

        condor.waitForAllJobsToRun(jobNumbers)

        # wait for all jobs to launch
        self.filewaiter.waitForAllFiles()

        eventBrokerHost = self.prodPolicy.get("eventBrokerHost")
        shutdownTopic = self.wfPolicy.get("shutdownTopic")

        self.workflowMonitor = VanillaCondorWorkflowMonitor(eventBrokerHost, shutdownTopic, self.runid, self.logger)
        if statusListener != None:
            self.workflowMonitor.addStatusListener(statusListener)
        self.workflowMonitor.startMonitorThread(self.runid)
        return self.workflowMonitor

    ##
    #
    #
    def writeJobFile(self, jobNumber, jobFile):
        if self.logger != None:
            self.logger.log(Log.DEBUG, "VanillaCondorWorkflowLauncher:writeJobFile: writing %s" % jobFile)
        jobfile = open(jobFile, 'w')
        jobfile.write("%s.0\n" % jobNumber)
        jobfile.close()

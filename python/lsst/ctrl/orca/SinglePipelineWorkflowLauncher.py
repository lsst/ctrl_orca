import sys, subprocess
from lsst.pex.logging import Log
from lsst.ctrl.orca.EnvString import EnvString
from lsst.ctrl.orca.WorkflowMonitor import WorkflowMonitor
from lsst.ctrl.orca.WorkflowLauncher import WorkflowLauncher

class SinglePipelineWorkflowLauncher(WorkflowLauncher):
    ##
    # @brief
    #
    def __init__(self, logger, wfPolicy):
        logger.log(Log.DEBUG, "SinglePipelineWorkflowLauncher:__init__")
        self.logger = logger
        self.wfPolicy = wfPolicy

    ##
    # @brief launch this workflow
    # TODO: Propose most of this configuration of the command should be moved into the configurator.
    # TODO: Propose that launch take a list of commands to be executed, passed in from the configurator.
    #
    def launch(self):
        self.logger.log(Log.DEBUG, "SinglePipelineWorkflowLauncher:launch")
        sys.exit(1)

        execPath = self.wfPolicy.get("configuration.framework.exec")
        launchcmd = EnvString.resolve(execPath)

        setupPath = self.wfPolicy.get("configuration.framework.environment")
        script = EnvString.resolve(setupPath)

        if orca.envscript == None:
            print "using policy defined environment setup"
        else:
            self.script = orca.envscript

        #
        # TODO:  Fix this -
        # self.dirs doesn't exist, because we need to call Directories...
        # which requires a runid... which is not accessible at this point
        # ideally, dirs is passed fully formed, since we had to create it for deployment,
        # or better yet, the whole command should just be passed in.
        self.script = os.path.join(self.dirs.get("work"), os.path.basename(self.script))

        filename = self.wfPolicy.get("shortName")+".paf"
    
        cmd = ["ssh", self.masterNode, "cd %s; source %s; %s %s %s -L %s" % self.dirs.get("work"), self.script, launchcmd, filename, self.runid, self.verbosity ]

        pid = os.fork()
        if not pid:
            os.execvp(self.cmd[0], self.cmd)
        os.wait()[0]

        self.workflowMonitor = WorkflowMonitor(self.logger)
        return self.workflowMonitor # returns WorkflowMonitor

    ##
    # @brief perform cleanup after workflow has ended.
    #
    def cleanUp(self):
        self.logger.log(Log.DEBUG, "SinglePipelineWorkflowLauncher:cleanUp")

    ##
    # @brief perform checks on validity of configuration of this workflow
    #
    def checkConfiguration(self, care):
        # the level of care taken in the checks.  In general, the higher
        # the number of checks that will be done.
        self.logger.log(Log.DEBUG, "SinglePipelineWorkflowLauncher:checkConfiguration")
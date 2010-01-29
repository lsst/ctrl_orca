from lsst.ctrl.orca.ProductionRunner import ProductionRunner

##
# @brief launches pipelines
#
class BasicProductionRunner(ProductionRunner):
    def __init__(self, runid, policy, pipelineManagers):
        self.runid = runid
        self.policy = policy
        self.pipelineManagers = pipelineManagers

    def runPipelines(self):
        for pipelineManager in self.pipelineManagers:
            pipelineManager.runPipeline()

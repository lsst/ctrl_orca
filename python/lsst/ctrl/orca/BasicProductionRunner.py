##
# @brief launches pipelines
#
class BasicProductionRunner:
    def __init__(self, pipelineManagers):
        self.pipelineManagers = pipelineManagers

    def runPipelines(self):
        for pipelineManager in self.pipelineManagers:
            pipelineManager.runPipeline()
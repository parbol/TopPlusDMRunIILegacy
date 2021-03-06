from CRABClient.UserUtilities import config
config = config()

config.section_("General")
config.General.transferLogs = True
#config.General.requestName = 'DMScalar_ttbar01j_mphi_500_mchi_1_July2019_AODSIM' 
config.General.requestName = 'DMscalar_Dilepton_top_tWChan_Mchi1_Mphi100_RunIIAutumn18_AODSIM_PrivateProd' 
config.General.workArea = 'crab_projects'


config.section_("JobType")
config.JobType.pluginName  = 'Analysis'
config.JobType.psetName = 'aodsim.py'
#config.JobType.maxMemoryMB = 500000


config.section_("Data")
config.Data.splitting       = 'FileBased'
config.Data.unitsPerJob = 1
#config.Data.outputDatasetTag = 'DMScalar_ttbar01j_mphi_500_mchi_1_July2019_AODSIM'
config.Data.outputDatasetTag = 'DMscalar_Dilepton_top_tWChan_Mchi1_Mphi100_RunIIAutumn18_AODSIM_PrivateProd'
config.Data.inputDBS = 'phys03'
config.Data.outLFNDirBase = '/store/user/cprieels/' 
config.Data.publication = True
config.Data.inputDataset = '/CRAB_PrivateMC/cprieels-DMscalar_Dilepton_top_tWChan_Mchi1_Mphi100_RunIIAutumn18_PREMIX_PrivateProd-96e2d90999375d8c542ea905b43803e1/USER'


config.section_("Site")
config.Site.storageSite = 'T2_ES_IFCA'

import ROOT
from subprocess import call
from os.path import isfile

from keras.models import Sequential
from keras.layers import Dense, Activation, Dropout
from keras.regularizers import l2
from keras.optimizers import SGD, RMSprop, Adam
from keras.models import load_model
#from keras.utils import plot_model

import optparse, os, fnmatch, sys
from array import array

# ===========================================
# Arguments to be updated
# ===========================================

#Training variables
#variables = ["PuppiMET_pt", "mt2ll", "totalET", "dphill", "dphillmet", "Lepton_pt[0]", "Lepton_pt[1]", "mll", "nJet", "nbJet", "mtw1", "mtw2", "mth", "Lepton_eta[0]", "Lepton_eta[1]", "Lepton_phi[0]", "Lepton_phi[1]", "thetall", "thetal1b1", "thetal2b2", "dark_pt", "overlapping_factor", "reco_weight"] #cosphill missing, mt2bl as well
#variables = ["PuppiMET_pt", "MET_significance", "mll", "mt2ll", "mt2bl", "dphillmet", "Lepton_pt[0]", "Lepton_pt[1]", "Lepton_eta[0]", "Lepton_eta[1]", "dark_pt", "overlapping_factor", "reco_weight", "cosphill", "nbJet"] 
variables = ["PuppiMET_pt", "mt2ll", "dphillmet", "dark_pt", "nbJet"] 

trainPercentage = 50
normalizeProcesses = True #Normalize all the processes to have the same input training events in each case

#=========================================================================================================
# HELPERS
#=========================================================================================================
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

#Progress bar
def updateProgress(progress):
    barLength = 20 # Modify this to change the length of the progress bar
    status = ""
    if isinstance(progress, int):
        progress = float(progress)
    if not isinstance(progress, float):
        progress = 0
        status = "error: progress var must be float\r\n"
    if progress < 0:
        progress = 0
        status = "Halt...\r\n"
    if progress >= 1:
        progress = 1
        status = "Done!\r\n"
    block = int(round(barLength*progress))
    text = "\rProgress: [{0}] {1}% {2}".format( "#"*block + "-"*(barLength-block), progress*100, status)
    sys.stdout.write(text)
    sys.stdout.flush()

def splitByProcess(inputFiles, test = False, background = False):
    processes = [] #List of dictionnaries with the different processes as keys and a list of files as values
    
    for inputFile in inputFiles:
        #process = "_".join(inputFile.split("_")[1:5]) #TODO: try to find a better way to estimate the process?
        start = "nanoLatino_"
        end = "__part"
        process = inputFile[inputFile.find(start)+len(start):inputFile.rfind(end)].replace('_ext', '')

        #However, at least for now, let's group all the background processes if the option is set
        if background:
            process = 'backgrounds'
        else: #Only group the single top process together
            if 'ST' in process: process = 'ST'

        alreadyFound = [i for i, d in enumerate(processes) if process in d.keys()]
        if len(alreadyFound) == 0:
            processes.append({process: [inputFile]})
        else:
            if not test or len(processes[alreadyFound[0]][process]) < 30:
                processes[alreadyFound[0]][process].append(inputFile)

    return processes

#=========================================================================================================
# TRAINING
#=========================================================================================================
def trainMVA(baseDir, inputDir, year, backgroundFiles, signalFiles, test):
    """
    Function used to train the MVA based on the signal given
    """

    massPoint = signalFiles[0].split("_")[3:9]
    massPoint = "_".join(massPoint).replace(".root", "")

    #Move to the correct directory to save the model and its weights
    outputDirTraining = baseDir + "/" + str(year) + "/" + massPoint + "/training/"
    outputDirWeights = baseDir + "/" + str(year) + "/" + massPoint
    try:
        os.stat(outputDirTraining)
    except:
        os.makedirs(outputDirTraining)
    output = ROOT.TFile.Open(outputDirTraining+'TMVA.root', 'RECREATE')

    try:
        os.stat(outputDirWeights)
    except:
        os.makedirs(outputDirWeights)

    # ===========================================
    # Load data
    # ===========================================
    os.chdir(outputDirWeights)
    dataloader = ROOT.TMVA.DataLoader('dataset')
    for variable in variables:
        dataloader.AddVariable(variable)
        
    #Let's know try to find out how many signal and background processes have been passed as argument
    signalProcesses = splitByProcess(signalFiles, test, False)
    backgroundProcesses = splitByProcess(backgroundFiles, test, False)

    print(bcolors.WARNING + "\n --> I found " + str(len(signalProcesses)) + " signal processes and " + str(len(backgroundProcesses)) + " background processes.")
    print("Please check if these numbers seem to be correct! \n" + bcolors.ENDC)

    #canvas = ROOT.TCanvas("canvas")
    #canvas.cd()

    #Now add all the files to the corresponding processes in the dataloader and define the testing and training subsets
    numberSignals = len(signalProcesses)
    numberProcesses = len(signalProcesses) + len(backgroundProcesses)

    signalEvents =[]
    backgroundEvents = []
    minEvents = 999999999 #Used to have exactly the same number of events for each process toa void biases

    for index in range(len(signalProcesses)):

        signalFiles = signalProcesses[index].values()[0]
        signalChain = ROOT.TChain("Events")

        for signalFile in signalFiles:
            signalChain.AddFile(inputDir+signalFile)

        signalEvents.append(signalChain.GetEntries())
        if signalChain.GetEntries() < minEvents: 
            minEvents = signalChain.GetEntries()

        dataloader.AddTree(signalChain, 'Signal' + str(index))

    for index in range(len(backgroundProcesses)):

        backgroundFiles = backgroundProcesses[index].values()[0]
        backgroundChain = ROOT.TChain("Events")

        for backgroundFile in backgroundFiles:
            backgroundChain.AddFile(inputDir+backgroundFile)

        backgroundEvents.append(backgroundChain.GetEntries())
        if backgroundChain.GetEntries() < minEvents: 
            minEvents = backgroundChain.GetEntries()

        dataloader.AddTree(backgroundChain, 'Background' + str(index))

    # ===========================================
    # TMVA setup
    # ===========================================

    ROOT.TMVA.Tools.Instance()
    ROOT.TMVA.PyMethodBase.PyInitialize()
    if numberSignals > 1:
        factory = ROOT.TMVA.Factory('TMVAClassification', output, '!V:!Silent:Color:DrawProgressBar:AnalysisType=multiclass')
    else:
        factory = ROOT.TMVA.Factory('TMVAClassification', output, '!V:!Silent:Color:DrawProgressBar:AnalysisType=Classification')

    testPercentage = 100 - trainPercentage

    dataloaderOptions = ''
    for i, signalProcess in enumerate(signalProcesses):

        if normalizeProcesses:
            numberEvents = minEvents
        else:
            numberEvents = signalEvents[i]

        dataloaderOptions = dataloaderOptions + ':nTrain_Signal' + str(i) + '=' + str(int(numberEvents*trainPercentage/100)) + ':nTest_Signal' + str(i) + '=' + str(int(numberEvents*testPercentage/100)) #TOCHECK: for now, we consider a 50%/50% splitting

    for i, backgroundProcess in enumerate(backgroundProcesses):

        dataloaderOptions = dataloaderOptions + ':nTrain_Background' + str(i) + '=' + str(int(numberEvents*trainPercentage/100)) + ':nTest_Background' + str(i) + '=' + str(int(numberEvents*testPercentage/100)) #TOCHECK: for now, we consider a 50%/50% splitting

    dataloader.PrepareTrainingAndTestTree(ROOT.TCut(''), dataloaderOptions + ':SplitMode=Random:NormMode=EqualNumEvents:!V')

    # ===========================================
    # Keras model with grid search
    # ===========================================
    model = Sequential()
    model.add(Dense(20, activation='relu', input_dim=len(variables)))
    model.add(Dense(15, activation='relu'))
    model.add(Dense(10, activation='relu'))
    model.add(Dense(5, activation='relu'))
    model.add(Dense(numberProcesses, activation='softmax'))

    # Set loss and optimizer and save the model
    model.compile(loss='categorical_crossentropy', optimizer=Adam(0.005), metrics=['accuracy', 'mse'])
    model.save(outputDirTraining+'Adam1.h5')
    model.summary()

    model.compile(loss='categorical_crossentropy', optimizer=Adam(0.001), metrics=['accuracy', 'mse'])
    model.save(outputDirTraining+'Adam2.h5')
    model.summary()

    model.compile(loss='categorical_crossentropy', optimizer=Adam(0.0005), metrics=['accuracy', 'mse'])
    model.save(outputDirTraining+'Adam3.h5')
    model.summary()

    #Repeat 2016 analysis
    model = Sequential()
    model.add(Dense(15, activation='relu', input_dim=len(variables)))
    model.add(Dense(10, activation='relu'))
    model.add(Dense(5, activation='relu'))
    model.add(Dense(numberProcesses, activation='softmax'))

    model.compile(loss='categorical_crossentropy', optimizer=Adam(0.005), metrics=['accuracy', 'mse'])
    model.save(outputDirTraining+'Juan.h5')
    model.summary()

    # Book method
    #factory.BookMethod(dataloader, ROOT.TMVA.Types.kBDT, 'BDT', 'NTrees=300:BoostType=Grad:Shrinkage=0.2:MaxDepth=4:ncuts=1000000:MinNodeSize=1%:!H:!V')
    factory.BookMethod(dataloader, ROOT.TMVA.Types.kPyKeras, 'PyKeras', 'H:!V:FilenameModel=' + outputDirTraining + 'Juan.h5:FilenameTrainedModel=' + outputDirTraining + 'JuanTrained.h5:NumEpochs=200:BatchSize=200:VarTransform=N')
    #factory.BookMethod(dataloader, ROOT.TMVA.Types.kBDT, 'BDT', 'NTrees=300:BoostType=Grad:Shrinkage=0.2:MaxDepth=4:ncuts=50000:MinNodeSize=1%:!H:!V')
    #factory.BookMethod(dataloader, ROOT.TMVA.Types.kMLP, 'Juan', 'H:!V:NeuronType=sigmoid:NCycles=50:VarTransform=Norm:HiddenLayers=6,3:TestRate=3:LearningRate=0.005')

    # ===========================================
    # Run training, test and evaluation
    # ===========================================
    
    factory.TrainAllMethods()
    factory.TestAllMethods()
    factory.EvaluateAllMethods()


#=========================================================================================================
# APPLICATION
#=========================================================================================================
def evaluateMVA(baseDir, inputDir, filename, massPoints, year, test):
    """
    Function used to evaluate the MVA after being trained
    """

    # ===========================================
    # Setup TMVA
    # ===========================================
    ROOT.TMVA.Tools.Instance()
    ROOT.TMVA.PyMethodBase.PyInitialize()

    reader = ROOT.TMVA.Reader("Color:!Silent")
    for variable in variables:
        reader.AddVariable(variable, array('f',[0.]))    

    #Write the new branches in the tree
    rootfile = ROOT.TFile.Open(inputDir+filename, "UPDATE")
    inputTree = rootfile.Get("Events")

    for massPoint in massPoints:

        weightsDir = baseDir + "/" + str(year) + "/" + massPoint

        #reader.BookMVA("BDT", weightsDir + "/dataset/weights/TMVAClassification_BDT.weights.xml")
        reader.BookMVA("PyKeras", weightsDir + "/dataset/weights/TMVAClassification_PyKeras.weights.xml")

        PyKeras_output = array("f", [0.])
        inputTree.Branch("PyKeras_output", PyKeras_output, "PyKeras_output/F")

        nEvents = rootfile.Events.GetEntries()
        if test:
            nEvents = 1000

        for index, ev in enumerate(rootfile.Events):
        
            if index % 100 == 0: #Update the loading bar every 100 events
                updateProgress(round(index/float(nEvents), 2))
    
            #For testing only
            if test and index == nEvents:
                break

            #BDTValue = reader.EvaluateMVA("BDT")
            #BDT_output[0] = BDTValue
            PyKerasValue = reader.EvaluateMVA("PyKeras")
            PyKeras_output[0] = PyKerasValue

            inputTree.Fill()

    inputTree.Write()
    rootfile.Close()


    
if __name__ == "__main__":

    # ===========================================
    # Argument parser
    # ===========================================
    parser = optparse.OptionParser(usage='usage: %prog [opts] FilenameWithSamples', version='%prog 1.0')
    parser.add_option('-s', '--signalFiles', action='store', type=str, dest='signalFiles', default=[], help='Name of the signal files to be used to train the MVA')
    parser.add_option('-b', '--backgroundFiles', action='store', type=str, dest='backgroundFiles', default=[], help='Name of the background files samples to train the MVA')
    parser.add_option('-f', '--filename', action='store', type=str, dest='filename', default='', help='Name of the file to be evaluated')
    parser.add_option('-i', '--inputDir', action='store', type=str, dest='inputDir', default="") 
    parser.add_option('-d', '--baseDir', action='store', type=str, dest='baseDir', default="/afs/cern.ch/user/c/cprieels/work/public/TopPlusDMRunIILegacy/CMSSW_10_4_0/src/neuralNetwork/")
    parser.add_option('-m', '--massPoints', action='store', type=str, dest='massPoints', default="scalar_LO_Mchi_1_Mphi_100")
    parser.add_option('-y', '--year', action='store', type=int, dest='year', default=2018)
    parser.add_option('-e', '--evaluate', action='store_true', dest='evaluate') #Evaluate the MVA or train it?
    parser.add_option('-t', '--test', action='store_true', dest='test') #Only run on a single file
    (opts, args) = parser.parse_args()

    signalFiles     = opts.signalFiles
    backgroundFiles = opts.backgroundFiles
    filename = opts.filename
    inputDir = opts.inputDir
    baseDir = opts.baseDir
    massPoints= opts.massPoints
    year = opts.year
    evaluate = opts.evaluate
    test = opts.test

    #To evaluate the MVA, we pass as argument one file name each time, to parallelize the jobs
    if(evaluate):
        #The mass points to be added to the trees are also passed as comma separated values
        massPointsList = [str(item) for item in massPoints.split(",")]

        evaluateMVA(baseDir, inputDir, filename, massPointsList, year, test)

    else: #To train, we need to pass a list containing all the files at once

        #Split the comma separated string for the files into lists
        signalFiles = [str(item) for item in signalFiles.split(',')]
        backgroundFiles = [str(item) for item in backgroundFiles.split(',')]
            
        trainMVA(baseDir, inputDir, year, backgroundFiles, signalFiles, test)

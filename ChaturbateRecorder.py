import time, datetime, os, sys, requests, configparser, re, subprocess, json
from bs4 import BeautifulSoup
if os.name == 'nt':
    import ctypes
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
from queue import Queue
from livestreamer import Livestreamer
from threading import Thread

Config = configparser.ConfigParser()
Config.read(sys.path[0] + "/config.conf")
save_directory = Config.get('paths', 'save_directory')
wishlist = Config.get('paths', 'wishlist')
logfilename = Config.get('paths', 'logfile')
interval = int(Config.get('settings', 'checkInterval'))
directory_structure = Config.get('paths', 'directory_structure').lower()
postProcessingCommand = Config.get('settings', 'postProcessingCommand')
try:
    postProcessingThreads = int(Config.get('settings', 'postProcessingThreads'))
except ValueError:
    pass
completed_directory = Config.get('paths', 'completed_directory').lower()

def now():
    return '[' + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + ']'

recording = []
wanted = []

def startRecording(model):
    global postProcessingCommand
    global processingQueue
    try:
        result = requests.get('https://chaturbate.com/api/chatvideocontext/{}/'.format(model)).json()
        session = Livestreamer()
        session.set_option('http-headers', "referer=https://www.chaturbate.com/{}".format(model))
        streams = session.streams("hlsvariant://{}".format(result['hls_source'].rsplit('?')[0]))
        stream = streams["best"]
        fd = stream.open()
        now = datetime.datetime.now()
        filePath = directory_structure.format(path=save_directory, model=model, 
                                              seconds=now.strftime("%S"), minutes=now.strftime("%M"), 
                                              hour=now.strftime("%H"), day=now.strftime("%d"), 
                                              month=now.strftime("%m"), year=now.strftime("%Y"))
        directory = filePath.rsplit('/', 1)[0]+'/'
        if not os.path.exists(directory):
            os.makedirs(directory)
        if model in recording: return
        with open(filePath, 'wb') as f:
            recording.append(model)
            while model in wanted:
                try:
                    data = fd.read(1024)
                    f.write(data)
                except:
                    f.close()
                    break
        if postProcessingCommand:
            processingQueue.put({'model':model, 'path':filePath})
        elif completed_directory:
            finishedDir = completed_directory.format(path=save_directory, model=model,
                        seconds=now.strftime("%S"),
                        minutes=now.strftime("%M"),hour=now.strftime("%H"), day=now.strftime("%d"),
                        month=now.strftime("%m"), year=now.strftime("%Y"))

            if not os.path.exists(finishedDir):
                os.makedirs(finishedDir)
            os.rename(filePath, finishedDir+'/'+filePath.rsplit['/',1][0])
    except: pass
    finally:
        if model in recording:recording.remove(model)
def postProcess():
    global processingQueue
    global postProcessingCommand
    while True:
        while processingQueue.empty():
            time.sleep(1)
        parameters = processingQueue.get()
        model = parameters['model']
        path = parameters['path']
        filename = path.rsplit('/', 1)[1]
        directory = path.rsplit('/', 1)[0]+'/'
        subprocess.run(postProcessingCommand.split() + [path, filename, directory, model])

def getOnlineModels():
    online = []
    global wanted
      
    try:
        url = 'https://camspider.com/'
        html_text = requests.get(url).text
        soup = BeautifulSoup(html_text, 'html.parser')
        result = soup.find('script', id='__NEXT_DATA__').string
#        result = soup.select("#__NEXT_DATA__")[0]
#        result = result.text
#        print(result)
        result = json.loads(result)
        result = result['props']['pageProps']
        online.extend([m['username'].lower() for m in result['rooms']])

#	Add an additional check on chaturbate.com's main page, as camspider 
#	does not find all online models (example: x__rose__x)

        url = 'https://chaturbate.com/'
        html_text = requests.get(url).text
        soup = BeautifulSoup(html_text, 'html.parser')
        room_list = soup.find('ul', id='room_list')
        rooms = room_list.find_all('li', {'class': 'room_list_room'})
        for r in rooms:
            href = r.find('a')
            if (href):
                model = href.get('data-room')
                if model not in online:
                    online.append(model)
#        print(online)
                
    except Exception as e:
        print(e)
        pass
        
    f = open(wishlist, 'r')
    wanted = list(set(f.readlines()))
    wanted = [m.strip('\n').split('chaturbate.com/')[-1].lower().strip().replace('/', '') for m in wanted]
    #wantedModels = list(set(wanted).intersection(online).difference(recording))
    '''new method for building list - testing issue #19 yet again'''
#    print(wanted)
#    print("\nONLINE\n")
#    print(online)
#    print("\nRECORDING:\n")
#    print(recording)
    wantedModels = [m for m in (list(set(wanted))) if m in online and m not in recording]
    for theModel in wantedModels:
        thread = Thread(target=startRecording, args=(theModel,))
        thread.start()
    f.close()

def onlineModelsIsChanged(previousOnlineModels, newOnlineModels):
    if (len(previousOnlineModels) != len(newOnlineModels)):
        return True
    for i in range(len(previousOnlineModels)):
        if (previousOnlineModels[i] != newOnlineModels[i]):
            return True
    return False

if __name__ == '__main__':
    print()
    if postProcessingCommand != "":
        processingQueue = Queue()
        postprocessingWorkers = []
        for i in range(0, postProcessingThreads):
            t = Thread(target=postProcess)
            postprocessingWorkers.append(t)
            t.start()
    logfile = open(logfilename, "a+")
    logfile.write("\n\n" + now() + " ########## Starting ChaturbateRecorder4Docker ##########\n")
    logfile.close()
    recordingModels = []
    while True:
        getOnlineModels()
        print(now(), " The following models are being recorded: {}".format(recording), end="\r")
        if onlineModelsIsChanged(recordingModels, recording):
            logfile = open(logfilename, "a+")
            logfile.write(now() + " The following models are being recorded: {}\n".format(recording))
            logfile.close()
            print( now(),"{} model(s) are being recorded. Getting list of online models now".format(len(recording)))        
            recordingModels = recording
#        getOnlineModels()
#        for i in range(interval, 0, -1):
#            sys.stdout.write("\033[K")
#            print(now(), "{} model(s) are being recorded. Next check in {} seconds".format(len(recording), i))
#            sys.stdout.write("\033[K")
#            print("The following models are being recorded: {}".format(recording), end="\r")
        time.sleep(interval)

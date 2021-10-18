from flask import Flask
import requests
from requests.exceptions import Timeout
import json
import configparser
from apscheduler.schedulers.background import BackgroundScheduler
import time

app = Flask(__name__)

# read variables from config
credential = configparser.ConfigParser()
credential.read('cred')

APIKEY = credential['Meraki']['APIkey']
SourceSaaSLink = credential['Meraki']['SourceSaaSLink']

organizationId = credential['Meraki']['organizationId']
networkId = credential['Meraki']['networkId']

PAYLOAD = []

DEF_TIMEOUT = 10

requests.packages.urllib3.disable_warnings()

@app.route("/", methods=['GET'])
def index():
    return ("App is running"), 200


def workOnObjectAndPolicy(data):
    global PAYLOAD
    PAYLOAD = []
    with open("newIPList.txt", "r") as jsonFile:

        jsonObject = json.load(jsonFile)
        jsonFile.close()

    for itemIP in jsonObject:
        # in case of fqdn
        try:
            urls = itemIP["urls"]
            for url in itemIP["urls"]:
                if str(itemIP).find('tcpPorts') != -1: 
                    ports = itemIP["tcpPorts"]
                    appendL3FirewallRulesJson("Comment add " + str(url), "tcp", itemIP["tcpPorts"], url)
                else:
                    ports = itemIP["udpPorts"]
                    appendL3FirewallRulesJson("Comment add " + str(url), "udp", itemIP["udpPorts"], url)
        except KeyError:
            pass
        # in case of cidr
        try:
            ips = itemIP["ips"]
            for ip in itemIP["ips"]:  
                if isIPv4(ip):
                    if str(itemIP).find('tcpPorts') != -1: 
                        ports = itemIP["tcpPorts"]
                        appendL3FirewallRulesJson("Comment add " + str(ip), "tcp", itemIP["tcpPorts"], ip)
                    else:
                        ports = itemIP["udpPorts"]
                        appendL3FirewallRulesJson("Comment add " + str(ip), "udp", itemIP["udpPorts"], ip)
        except KeyError:
            pass

    addL3FirewallRules(PAYLOAD)
    
def addL3FirewallRules(data):
    API_Server = "https://api.meraki.com/"

    API_Endpoint = API_Server + "api/v0/"
    Path = "networks/{}/l3FirewallRules/".format(networkId)
    API_Resource =  API_Endpoint + Path
    
    body = {"rules": data}

    with open("body.txt", "w") as f:
        f.write(str(body).replace("\'", "\""))
    body_json = json.dumps(body)

    
    HTTP_Request_header = {
    'X-Cisco-Meraki-API-Key': APIKEY,
    'Content-Type': 'application/json'
    }

    createObject = requests.put(API_Resource, data=body_json, headers=HTTP_Request_header, timeout=DEF_TIMEOUT)

    if createObject.status_code == 200:
        try:
            text = createObject.json()
            addLogs("addL3FirewallRules " + str(text))
            print("L3FirewallRules Updated")
        except json.decoder.JSONDecodeError:
            print("Error JSONDecodeError")
            return("Error JSONDecodeError")
        return text
    elif createObject.status_code == 429:
        time.sleep(30)
        addL3FirewallRules(data)
    else:
        addLogs("addL3FirewallRules error " + str(createObject.status_code))


def appendL3FirewallRulesJson(comment, protocol, destPorts, urlIP):
    global PAYLOAD
    if urlIP.find('*-') != -1 or urlIP.find('.*.') != -1 or urlIP.find('*cdn.onenote.net') != -1:
        return 1  
    PAYLOAD.append({
          "comment": comment,
          "policy": "allow",
          "protocol": protocol,
          "srcPort": "Any",
          "srcCidr": "Any",
          "destPort": destPorts,
          "destCidr": urlIP,
          "syslogEnabled": "False"
      })


def getCompareSaaSAdresses():
    IPjsonList = requests.get(SourceSaaSLink, timeout=DEF_TIMEOUT).json()

    with open("newIPlist.txt", "r+") as f:
        f.seek(0) 
        f.write(str(IPjsonList).replace("\'", "\"").replace("False", '''"False"''').replace("True", '''"True"'''))
        newData = str(IPjsonList).replace("\'", "\"").replace("False", '''"False"''').replace("True", '''"True"''')
        f.truncate()
    
    with open("IPlist.txt", "r+") as p:
        oldData = p.read()
        print('Changes dont detected')
        if oldData != newData or oldData == '':
            print('Changes detected')
            p.seek(0)
            p.write(str(IPjsonList).replace("\'", "\"").replace("False", '''"False"''').replace("True", '''"True"'''))
            p.truncate()
            workOnObjectAndPolicy(newData)

def isIPv4(ip):
    if ip.find('/') >= 0:
        stIP = ip.split('/')
        s = stIP[0]
    pieces = s.split('.')
    if len(pieces) != 4: 
        return False
    try: 
        return all(0<=int(p)<256 for p in pieces)
    except ValueError: 
        return False

def addLogs(text):
    with open("log.txt", "a+") as f:
        f.write('\n' + text)


print("Running...")
sched = BackgroundScheduler(daemon=True)
sched.add_job(getCompareSaaSAdresses, 'interval', seconds=15)
# Set interval also in format days=3, minutes=5 seconds=15
sched.start()
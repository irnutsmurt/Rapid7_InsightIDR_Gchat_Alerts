import requests
import json
import configparser
import os
import gzip
import shutil
import httplib2
import logging
import time
import pytz
from httplib2 import Http
from datetime import datetime, timedelta
from logging.handlers import TimedRotatingFileHandler

class CustomTimedRotatingFileHandler(TimedRotatingFileHandler):
    def __init__(self, dir_log, when='h', interval=1, backupCount=0, encoding=None, delay=False, utc=False, atTime=None):
        self.dir_log = dir_log
        self.current_time = datetime.now()
        dir_name = os.path.dirname(self.dir_log)
        if not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)

        super().__init__(self.dir_log, when=when, interval=interval, backupCount=backupCount, encoding=encoding, delay=delay, utc=utc, atTime=atTime)

    def getArchiveName(self):
        # Replace the original filename with the formatted one when it's time to rotate logs
        return f"{self.dir_log}.{self.current_time.strftime('%Y-%m-%d')}.log.gz"

    def doRollover(self):
        # Do a rollover, as described in the base FileHandler class,
        # but afterwards, put the log in the appropriate year and month folder and compress it
        super().doRollover()

        old_log = self.getArchiveName().replace(".gz", "")
        if os.path.exists(old_log):
            os.renames(old_log, self.getArchiveName())
            with open(self.getArchiveName(), 'rb') as f_in:
                with gzip.open(self.getArchiveName(), 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            os.remove(old_log)

    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None

        # get the time that this sequence started at and make it a TimeTuple
        currentTime = int(time.time())
        dstNow = time.localtime(currentTime)[-1]
        t = self.rolloverAt - self.interval
        if self.utc:
            timeTuple = time.gmtime(t)
        else:
            timeTuple = time.localtime(t)
            dstThen = timeTuple[-1]
            if dstNow != dstThen:
                if dstNow:
                    addend = 3600
            else:
                addend = -3600
            timeTuple = time.localtime(t + addend)

        # Compose the directory and filename
        year_dir = os.path.join(self.dir_log, str(timeTuple.tm_year))
        month_dir = os.path.join(year_dir, str(timeTuple.tm_mon).zfill(2))
        dfn = os.path.join(month_dir, self.baseFilename + "." + time.strftime(self.suffix, timeTuple))

        os.makedirs(month_dir, exist_ok=True)

        if os.path.exists(dfn):
            os.remove(dfn)

        # Issue 18940: A file may not have been created if delay is True.
        if os.path.exists(self.baseFilename):
            os.rename(self.baseFilename, dfn)
            with open(dfn, 'rb') as f_in, gzip.open(dfn + '.gz', 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
            os.remove(dfn)

        if self.backupCount > 0:
            for s in self.getFilesToDelete():
                os.remove(s)

        self.mode = 'w'
        self.stream = self._open()

        
    def getFilesToDelete(self):
        """
        Determine the files to delete when rolling over.
        """
        dirName, baseName = os.path.split(self.baseFilename)
        fileNames = os.listdir(dirName)
        result = []
        prefix = baseName + "."
        plen = len(prefix)
        for fileName in fileNames:
            if fileName[:plen] == prefix:
                suffix = fileName[plen:]
                if self.extMatch.match(suffix):
                    result.append(os.path.join(dirName, fileName))
        result.sort()
        if len(result) < self.backupCount:
            result = []
        else:
            result = result[:len(result) - self.backupCount]
        return result

# define logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# set up console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# set up file handler
file_handler = CustomTimedRotatingFileHandler(dir_log='log/alert.log', when='midnight', backupCount=365, delay=True)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Add debug logs
logger.debug(f"Logging level: {logging.getLevelName(logger.getEffectiveLevel())}")
logger.debug(f"Console handler logging level: {logging.getLevelName(console_handler.level)}")

# read the configuration from config.ini file
config = configparser.ConfigParser()
config.read('config.ini')

# get the InsightIDR API key and region from the config file
insightidr_api_key = config['insightidr']['api_key']
region = config['insightidr']['region']

# get priority_levels from config
priority_levels = config['alerts_field']['priority_levels'].split(',')

# set variable for sent alerts
sent_alert_rrns_file = 'sent_alert_rrns.txt'

# set the InsightIDR API endpoint URL
#pacific = pytz.timezone('US/Pacific')
#end_time = datetime.now(pacific).strftime('%Y-%m-%dT%H:%M:%SZ') # Current time
#start_time = (datetime.now(pacific) - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ') # One hour ago
now = datetime.utcnow()
start_time = (now - timedelta(minutes=5)).isoformat() + 'Z'  # 5 minute before now
end_time = now.isoformat() + 'Z'  # now

insightidr_url = f"https://{region}.api.insight.rapid7.com/idr/v2/investigations?filter=created_time>{start_time}&filter=created_time<{end_time}"

# set the InsightIDR API headers
insightidr_headers = {
    'X-Api-Key': insightidr_api_key,
    'Content-Type': 'application/json',
    'Accept-version': 'investigations-preview'
}


insightidr_url_v1 = f"https://{region}.api.insight.rapid7.com/idr/v1/investigations"

insightidr_headers_v1 = {
    'X-Api-Key': insightidr_api_key,
    'Content-Type': 'application/json',
}

# set the file path and name for the JSON alert files
raw_alerts_file = 'raw_alerts.json'
formatted_alerts_file = 'formatted_alerts.json'

# define Http object
http_obj = Http()

def get_raw_alerts():
    # get the list of investigations from InsightIDR
    response = requests.get(insightidr_url, headers=insightidr_headers)

    if response.status_code != 200:
        logger.error(f"Failed to get investigations from InsightIDR: {response.reason}")
        return None

    # parse the response and return the list of investigations
    investigations = response.json()['data']
    # Filter out the alerts based on priority_levels
    investigations = [alert for alert in investigations if alert['priority'] in priority_levels]
    return investigations

def get_raw_alerts_v1():
    response = requests.get(insightidr_url_v1, headers=insightidr_headers_v1)
    if response.status_code != 200:
        logger.error(f"Failed to get investigations from InsightIDR V1 API: {response.reason}")
        return None
    investigations_v1 = response.json()['data']
    return investigations_v1


def format_alerts(alerts, alerts_v1):
    message = ''
    for alert in alerts:
        priority = alert.get('priority')
        created_time = alert.get('created_time')
        title = alert.get('title')
        rrn = alert.get('rrn')
        matching_alert_v1 = next((a for a in alerts_v1 if a['rrn'] == rrn), None)
        id_v1 = matching_alert_v1['id'] if matching_alert_v1 else ''
        url = f"https://us2.idr.insight.rapid7.com/op/"place your companyid here"#/investigations/{id_v1}" if id_v1 else ''
        message += f"Investigation URL: {url}\n"
        message += f"Created Time: {created_time}\n"
        message += f"Priority: {priority}\n"
        message += f"Title: {title}\n\n"

    data = {
        "text": message
    }

    return data


def save_formatted_alerts(payload):
    # save the formatted alerts to a file
    with open(formatted_alerts_file, 'w') as f:
        json.dump(payload, f, indent=4)
    logger.info(f"{len(payload['cards'])} formatted alerts saved to {formatted_alerts_file}")

def send_alerts_to_chat(payload, alert_rrns, sent_alert_rrns):
    global sent_alert_rrns_file
    # send the formatted alerts to Google Chat
    webhook_url = config['google_chat']['webhook_url']
    headers = {'Content-Type': 'application/json; charset=UTF-8'}
    response, content = http_obj.request(
        uri=webhook_url,
        method='POST',
        body=json.dumps(payload),
        headers=headers)

    if response.status == 200:
        logger.info(f"{len(alert_rrns)} alerts sent successfully to Google Chat")
        # add the RRNs of the sent alerts to the set of already-sent alert RRNs
        sent_alert_rrns.update(alert_rrns)
        # write the updated set of already-sent alert RRNs to the file
        with open(sent_alert_rrns_file, 'w') as f:
            f.writelines([rrn + '\n' for rrn in sent_alert_rrns])
    else:
        logger.error(f"Failed to send alerts to Google Chat: {response.reason}")


def main():
    global sent_alert_rrns_file
    global raw_alerts_file

    # read the RRNs of already-sent alerts from the file, if it exists
    sent_alert_rrns = set()
    sent_alert_rrns_file = 'sent_alert_rrns.txt'
    if os.path.isfile(sent_alert_rrns_file):
        with open(sent_alert_rrns_file, 'r') as f:
            for line in f:
                sent_alert_rrns.add(line.strip())
    else:
        with open(sent_alert_rrns_file, 'w') as f:
            pass  # create an empty file if it doesn't exist
        logger.info(f"Created new file: {sent_alert_rrns_file}")

    # get the list of raw alerts from InsightIDR
    raw_alerts = get_raw_alerts()
    raw_alerts_v1 = get_raw_alerts_v1()

    if raw_alerts is not None:
        # make sure the file exists, create it if not
        if not os.path.isfile(raw_alerts_file):
            with open(raw_alerts_file, 'w') as f:
                json.dump([], f, indent=4)
            logger.info(f"Created new raw alerts file: {raw_alerts_file}")

        # save the raw alerts to a file
        with open(raw_alerts_file, 'a') as f:
            json.dump(raw_alerts, f, indent=4)
        logger.info(f"{len(raw_alerts)} raw alerts downloaded to {raw_alerts_file}")
    else:
        logger.warning("No raw alerts found.")

    # Purge raw alerts file after processing
    with open(raw_alerts_file, 'w') as f:
        json.dump([], f, indent=4)
    logger.info(f"Raw alerts file '{raw_alerts_file}' purged after processing.")

    # read the RRNs of the last sent alerts from the file, if it exists
    last_sent_alert_rrns = []
    last_sent_alert_rrns_file = 'last_sent_alert_rrns.txt'
    if os.path.isfile(last_sent_alert_rrns_file):
        with open(last_sent_alert_rrns_file, 'r') as f:
            last_sent_alert_rrns = [line.strip() for line in f]

    # filter the alerts to exclude already-sent alerts
    new_alerts = [alert for alert in raw_alerts if alert['rrn'] not in sent_alert_rrns and alert['rrn'] not in last_sent_alert_rrns]
    logger.info(f"{len(new_alerts)} new alerts found after filtering")


    if new_alerts:
        logger.info(f"{len(new_alerts)} new alerts found.")
        # format the new alerts into a payload that Google Chat can read
        formatted_payload = format_alerts(new_alerts, raw_alerts_v1)

        # send the formatted alerts to Google Chat
        sent_alert_rrns_before = set(sent_alert_rrns)  # initialize sent_alert_rrns_before with the current value of sent_alert_rrns
        send_alerts_to_chat(formatted_payload, [alert['rrn'] for alert in new_alerts], sent_alert_rrns)

        # check if any new alerts were actually sent
        sent_alert_rrns_after = set(sent_alert_rrns)
        if sent_alert_rrns_after > sent_alert_rrns_before:
            logger.info(f"{len(new_alerts)} new alerts sent successfully to Google Chat")
        else:
            logger.warning("No new alerts sent to Google Chat.")
    else:
        logger.info("No new alerts found.")


while True:
    main()
    time.sleep(60)

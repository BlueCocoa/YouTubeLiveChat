#!/usr/bin/python3
# -*- coding: utf-8 -*-

import argparse
import csv
import json
import re
import time
from urllib import request

CONTINUATION = re.compile(r'Live chat replay"(?:.*?)continuation":"(.*?)"', re.MULTILINE)
LIVECHATREPLAYCONTINUATIONDATA = re.compile(r'liveChatReplayContinuationData"(?:.*?)continuation":"(.*?)"',
                                            re.MULTILINE)


class YouTubeLiveChatMessage(object):
    def __init__(self, content, is_paid):
        self.content = content
        self.is_paid = is_paid

    def text(self):
        if 'message' in self.content:
            msgComponents = self.content['message']['runs']
            texts = []
            for msg in msgComponents:
                if 'text' in msg:
                    texts.append(msg['text'])
            return " ".join(texts)
        else:
            return ""

    def timestamp(self):
        return self.content['timestampText']['simpleText']


class YouTubeLiveChat(object):
    def __init__(self, url: str, quiet=False):
        """Constructor
        @param url: str, full YouTube URL
        @param quiet: bool, supprese output
        """
        self.url = url
        self.quiet = quiet

    def parseYtInitialData(self, data):
        """Parse window["ytInitialData"]
        @param data, JSON Object
        @return msgs, list[YouTubeLiveChatMessage]
        """
        msgs = []
        if 'continuationContents' not in data:
            return msgs

        actionArray = data['continuationContents']['liveChatContinuation']['actions']
        for ac in actionArray:
            subactionArray = ac['replayChatItemAction']['actions']
            for sac in subactionArray:
                if 'addChatItemAction' in sac:
                    item = sac['addChatItemAction']['item']
                    if 'liveChatPaidMessageRenderer' in item:
                        msgs.append(YouTubeLiveChatMessage(item['liveChatPaidMessageRenderer'], True))
                    elif 'liveChatTextMessageRenderer' in item:
                        msgs.append(YouTubeLiveChatMessage(item['liveChatTextMessageRenderer'], True))
        return msgs

    def downloadAll(self, msg_callback, sleep_interval=1,
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.1 Safari/605.1.15'):
        """Download all live chat message
        @param msg_callback, callable, (msgs: list[YouTubeLiveChatMessage]) -> Any
        @param sleep_interval, int, interval between each fetch
        @param user_agent, str, user agent used in urllib request
        """
        nextURL = self.url
        count = 0
        while nextURL is not None:
            req = request.Request(nextURL, data=None, headers={'User-Agent': user_agent})
            with request.urlopen(req) as response:
                httpBody = response.read().decode('utf-8')
                matches = None
                if count == 0:
                    matches = CONTINUATION.findall(httpBody)
                else:
                    matches = LIVECHATREPLAYCONTINUATIONDATA.findall(httpBody)
                count += 1
                if len(matches) > 0:
                    nextURL = f"https://www.youtube.com/live_chat_replay?continuation={matches[0]}"
                    if not self.quiet:
                        print(f'[+] downloading page {count}')
                    time.sleep(sleep_interval)
                    if count > 1:
                        for line in httpBody.split("\n"):
                            line = line.strip()
                            if line.startswith('window["ytInitialData"]'):
                                jsonString = line[len('window["ytInitialData"] = '):-1]
                                data = json.loads(jsonString)
                                msg_callback(self.parseYtInitialData(data))
                else:
                    nextURL = None
                    if not self.quiet:
                        print("No more continuation param found")


def parsearg():
    parser = argparse.ArgumentParser()
    parser.add_argument("-u", "--url", type=str, help="Full YouTube URL")
    parser.add_argument("-o", "--output", type=str, help="Path to save live chats in CSV format")
    parser.add_argument("-q", "--quiet", action="store_true", help="Run quietly", default=False)
    return parser.parse_args()


if __name__ == '__main__':
    args = parsearg()

    def dump_to_csv(save_to: str):
        csvfile = open(save_to, 'w', newline='')
        writer = csv.DictWriter(csvfile, quoting=csv.QUOTE_MINIMAL, fieldnames=['timestamp', 'text'])
        writer.writeheader()
        line_written = [0]

        def _dump(msgs: [YouTubeLiveChatMessage]):
            for m in msgs:
                text = m.text().strip()
                if len(text) > 0:
                    writer.writerow({'timestamp': m.timestamp(), 'text': text})
                    line_written[0] += 1
            if not args.quiet:
                print(f'[+] total {line_written[0]} lines written')

        return _dump


    liveChat = YouTubeLiveChat(args.url, args.quiet)
    liveChat.downloadAll(dump_to_csv(args.output))

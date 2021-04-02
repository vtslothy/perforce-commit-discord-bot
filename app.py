import os
import subprocess
import time
import re
import random
import json
from discord_webhooks import DiscordWebhooks

class PerforceLogger():
    def __init__(self):
      """ Initializes a 1 second timer used to check if commits have been made.  """
      
      self.art_webhook_url = os.environ.get('DISCORD_ART_WEBHOOK_URL')
      self.code_webhook_url = os.environ.get('DISCORD_CODE_WEBHOOK_URL')
      self.general_webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')

      self.big_checkin_flavor = [ 'Whoah boy, this is big - ', 'Watch out, big one comin\' through - ', 'ohhhhh wow - ', 'big round of applause for this chonk - ', 'I can\' even count this high - ' ]
      self.medium_checkin_flavor = [ 'Looks like we got ourselves some new stuff here - ', 'Well check this out - ', 'clap clap clap - ', 'Arf arf - ', 'Wooooooo - ' ]
      self.small_checkin_flavor = [ 'Little changelist here - ', 'Gettin\' it done - ', 'Small one - ', 'I secrely like hamburgers - ', 'Well actually, ', 'Hey look at this! ', 'Ooh - ' ]

      self.global_store = {
        'latest_change': self.load_last_cl()
      }

    def load_last_cl(self):
        f = open( "lastcl.json", "r")
        data = json.load( f )
        lastCL = data['lastCL']
        print lastCL
        return lastCL

    def save_last_cl(self, cl):
        f = open( "lastcl.json", "w+")
        data = { "lastCL" : cl }
        json.dump( data, f )
        return

    def get_cl(self, summary):
      cl = re.findall( "\d+", summary )
      return cl[0]

    def check_p4(self):
      """ Runs the p4 changes command to get the latest commits from the server. """
      p4_changes = subprocess.Popen('p4 changes -t -m 1', stdout=subprocess.PIPE, shell=True)
      return p4_changes.stdout.read().decode('ISO-8859-1')

    def pick_random_string(self, stringArr ):
      idx = random.randint(0,len(stringArr)-1)
      return stringArr[idx]

    def flavor_for_files(self, fileList):
        length = len( fileList )
        if length > 100:
            output = self.pick_random_string(self.big_checkin_flavor)
        elif length < 4:
            output = self.pick_random_string(self.small_checkin_flavor)
        else:
            output = self.pick_random_string(self.medium_checkin_flavor)
        return output

    def get_changed_files(self, cl ):
          p4_filesChanged = subprocess.Popen('p4 files @=' + cl, stdout=subprocess.PIPE, shell=True)
          fileList = p4_filesChanged.stdout.read().decode('ISO-8859-1')
          fileList = fileList.splitlines()
          return fileList

    def get_file_category(self, ext):
        cats = { 
                "bat" : "misc",
                "cpp" : "code", "h" : "code", "c" : "code", 
                "uasset" : "asset", 
                "tga" : "art", "jpg" : "art", "psd" : "art", "mdl" : "art" 
                }
        if ext in cats.keys():
            return cats[ext]
        print "couldn't find " + ext + " in categories"
        return 'uncategorized'

    def get_file_extensions(self, fileList):
        exts = {}
        for file in fileList:
            extArr = re.findall( "\.([a-zA-Z_\-0-9]+)\#", file )
            ext = extArr[0]
            if ext in exts.keys():
                exts[ext] += 1
            else:
                exts[ext] = 1
            # print file + " is " + ext
        return sorted(exts.items(), key = lambda kv:(kv[1], kv[0]))

    def fill_in_message(self, message, change_type, file_ext_counts, flavor, desc):
        colorDesc = flavor + desc
        footer = change_type + ": " + file_ext_counts
        message.set_content(color=0xc8702a, description='`%s`' % (colorDesc))
        message.set_author(name='Perforce')
        message.set_footer(text='`%s`' % (footer), ts=True)
        print( colorDesc + "\n" + footer )
        #message.send()
        return

    def summarize_exts(self, file_exts ):
        types_of_changes = {}
        for ext in file_exts:
            cat = self.get_file_category( ext[0] )
            if cat in types_of_changes.keys():
                types_of_changes[cat] = types_of_changes[cat] + ext[1]
            else:
                types_of_changes[cat] = ext[1]

        i = 0
        summary = ""
        for changeType in types_of_changes.items():
            if i > 0:
                summary += ", "
            summary += str( changeType[1] ) + " " + changeType[0] + " files"
            i = i + 1
        return summary


    def broadcast_cl(self, cl):
        files_changed = self.get_changed_files( cl )
        file_exts = self.get_file_extensions( files_changed )
        file_ext_summary = self.summarize_exts( file_exts )

        change_type = 'unknown'
        if len( file_exts ) > 0:
            change_type = self.get_file_category( file_exts[0][0] )
        flavor = self.flavor_for_files( files_changed )

        p4_changes = subprocess.Popen('p4 describe -s -m 15 ' + cl, stdout=subprocess.PIPE, shell=True)
        desc = p4_changes.stdout.read().decode('ISO-8859-1')
        desc = re.sub( r'@[^ ]+ ', ' ', desc )
        desc = re.sub( r' by ', ' by @', desc )

        genMessage = DiscordWebhooks(self.general_webhook_url)
        self.fill_in_message( genMessage, change_type, file_ext_summary, flavor, desc )
        if change_type == "code":
            message = DiscordWebhooks(self.code_webhook_url)
            self.fill_in_message( message, change_type, file_ext_summary, flavor, desc )
        elif change_type == "art":
            message = DiscordWebhooks(self.art_webhook_url)
            self.fill_in_message( message, change_type, file_ext_summary, flavor, desc )
        return
        

    def check_for_changes(self, output):
      """ Figures out if the latest p4 change is new or should be thrown out. """
      cl = self.get_cl( output )
      if cl != self.global_store['latest_change']:
        self.global_store['latest_change'] = cl 
        self.save_last_cl( cl )

        if '*pending*' in output: 
          return ''

        else:
          return cl

      else: 
        return ''

    def post_changes(self):
      """ Posts the changes to the Discord server via a webhook. """
      output = self.check_p4()
      cl = self.check_for_changes(output)

      if cl != '':
        self.broadcast_cl( cl ) 

      else:
        return

if __name__ == "__main__":
  """ Initializes the application loop that checks Perforce for changes. """
  logger = PerforceLogger()
  timer = time.time()

  while True:
    logger.post_changes()
    time.sleep(1.0 - ((time.time() - timer) % 1.0))

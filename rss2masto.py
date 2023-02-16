#!/usr/bin/env python3

# Name: rss2masto.py
# Author: Leon Cowle - https://github.com/leoncowle or https://hachyderm.io/@leoncowle on Mastodon
# Copyright: 2023 Leon Cowle
# License: MIT (see LICENSE file)
# Version: 0.1

import bs4
import feedparser
import sqlite3
import sys
import hashlib
import requests
import re
import os
import configparser

####################### GLOBAL VARIABLES #######################
########### DO NOT EDIT THESE. EDIT rss2masto.ini INSTEAD ######
mastoHOST = ""
mastoBASE = ""
mastoTOKEN = ""
mastoURL = ""
mastoDB = ""
mastoINI = "rss2masto.ini"
debug = False   # this one you can edit, and change to False to suppress progress output
################################################################

def read_config():
  ''' read config from rss2masto.ini and store into global variables '''
  ''' yes i know global variables are bad, but for a small script like this, I'm ok with that :-) '''
  global mastoHOST
  global mastoTOKEN
  global mastoDB
  global mastoURL
  global mastoBASE
  config = configparser.ConfigParser()
  config.read(mastoINI)
  mastoHOST = config["GLOBAL"]["mastoHOST"]
  mastoDB = config["GLOBAL"]["mastoDB"]
  mastoBASE = "/api/v1/statuses"
  if config["GLOBAL"]["mastoTOKEN"]:
    mastoTOKEN = config["GLOBAL"]["mastoTOKEN"]
  elif "MASTOTOKEN" in os.environ:
    mastoTOKEN = os.environ["MASTOTOKEN"]
  else:
    print("No token found in rss2masto.ini or in MASTOTOKEN env variable. Exiting...")
    sys.exit(1)
  mastoURL = mastoHOST + mastoBASE + "?access_token=" + mastoTOKEN

def sql3_create_connection(db_file):
  """ create a database connection to a SQLite database """
  conn = None
  try:
    conn = sqlite3.connect(db_file)
  except sqlite3.Error as e:
    SystemExit(e)
  return conn

def sql3_create_table(conn):
  """ create our table if it doesn't exist yet """
  try:
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS seenposts (hash TEXT)")
    conn.commit()
  except sqlite3.Error as e:
    SystemExit(e)

def sql3_insert(conn, hashToAdd):
  """ add a new hash into the DB """
  try:
    c = conn.cursor()
    c.execute(f"INSERT INTO seenposts VALUES ('{hashToAdd}')")
  except sqlite3.Error as e:
    SystemExit(e)

def sql3_getAll(conn):
  """ get all existing entries in DB and return in dict """
  try:
    c = conn.cursor()
    rows = c.execute(f"SELECT * from seenposts").fetchall()
  except sqlite3.Error as e:
    SystemExit(e)

  hashes = {}
  for entry in rows:
    hashes[entry[0]] = True
  return hashes

class rss2masto():

  """ Class to crawl an RSS feed and post each new entry in it to Mastodon """

  def __init__(self, name, url, conn, existingHashes):
    self.name = name
    self.url = url
    self.conn = conn
    self.entryLink = None
    self.entryTitle = None
    self.siteURL = None
    self.existingHashes = existingHashes

  def _testURL(self, url):
    """ To avoid reinventing the wheel I'm re-using this regex, which is apparently from django src code 
        as per https://stackoverflow.com/questions/7160737/how-to-validate-a-url-in-python-malformed-or-not """
    urlregex = re.compile(
        r'^https?://'                                                                        # http:// or https:// (I removed 'ftp')
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' # domain...
        r'localhost|'                                                                        # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'                                               # ...or ip
        r'(?::\d+)?'                                                                         # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(urlregex, url) is not None

  def _mastoPOST(self):
    """ Post to Mastodon """
    headers = {'Content-Type':'application/x-www-form-URLencoded'}
    data = {'status':f'FROM: {self.name}\nMAIN URL: {self.siteURL}\n\nTITLE: {self.entryTitle}\n\n{self.entryLink}'}
    try:
      r = requests.post(mastoURL, headers=headers, data=data)
    except requests.exceptions.RequestException as e:
      raise SystemExit(e)

    if r.status_code != 200 and debug:
      print(r.text)
    
    return r.status_code == 200

  def process(self):
    """ Process a specific feed, using feedparser module """
    rssFeed = feedparser.parse(self.url)
    if rssFeed.status == 301 or rssFeed.status == 302:
      # We got a redirect response, let's see if we can grab the new suggested url (in rssFeed.href) instead...
      if self._testURL(rssFeed.href):
        if debug:
          print(f"{self.url} responded with 301/302 to {rssFeed.href}... Trying that instead...")
        rssFeed = feedparser.parse(rssFeed.href)
    if rssFeed.status != 200:
      print(f"Error crawling {self.url}... Skipping...")
      return
    self.siteURL = rssFeed.feed.link
    for entry in rssFeed.entries:
      # Determine whether to use entry.link or entry.id as the link to the RSS item
      # NOTE: 'guid' in the RSS item translates to 'id' in the feedparser entry dict
      self.entryLink = None
      if "id" in entry:
        # 'id' (i,e, 'guid') is present
        if self._testURL(entry.id):
          # And it's a valid URL
          if "guidislink" in entry and entry.guidislink == False:
            # guidislink ('isPermaLink' attribute from 'guid' element in RSS item) is present
            # and it's False, meaning the RSS provider is telling us NOT to use 'guid' ('id') as the link
            self.entryLink = entry.link
          else:
            # guidislink is either missing, or is True
            # and because we've already determined that entry.id is a valid URL, we can use it as the link
            self.entryLink = entry.id
      if not self.entryLink:
        # entryLink wasn't set above, so we'll simply default to the only option available to us, which is entry.link
        self.entryLink = entry.link

      self.entryTitle = entry.title.replace("\n","").replace("&nbsp;","")             # Some basic sanitizing that bs4 doesn't seem to do
      self.entryTitle = bs4.BeautifulSoup(self.entryTitle, features="html.parser").text    # And now let bs4 extract only the text (strip html tags)

      # Let's create a hash of our entryLink-entryTitle combo
      toHash = f"{self.entryLink}{self.entryTitle}"
      entrySHA256 = hashlib.sha256(toHash.encode())        # encode() converts the string into bytes to be accepted by the hash function.
      entryDigest = entrySHA256.hexdigest()                # hexidigest() returns the encoded data in hexadecimal format

      if entryDigest in self.existingHashes:
        # calculated hash is already in our DB, so we've seen this post before
        if debug:
          print(f"Skipping (already seen): {self.entryLink} {self.entryTitle}")
        continue

      if self._mastoPOST():
        # Our post to Mastodon was successful
        # Let's update dict and DB
        self.existingHashes[entryDigest] = True
        sql3_insert(self.conn, entryDigest)
        if debug:
          print(f"Successfully posted to Masto: {self.entryLink} {self.entryTitle}")

    # Commit once we've run through all the RSS items (entries)
    self.conn.commit()

# MAIN
if __name__ == '__main__':

  # Get configs from rss2masto.ini
  read_config()

  # Get DB connection
  conn = sql3_create_connection(mastoDB)

  # Create table (if needed)
  sql3_create_table(conn)

  # Get current DB entries
  existingHashes = sql3_getAll(conn)

  # Process feed(s)
  #rss2masto("<friendly-name>", "<feed url>", conn, existingHashes).process()
  #rss2masto("<friendly-name>", "<feed url>", conn, existingHashes).process()
  #rss2masto("<friendly-name>", "<feed url>", conn, existingHashes).process()
  #rss2masto("<friendly-name>", "<feed url>", conn, existingHashes).process()
  #rss2masto("<friendly-name>", "<feed url>", conn, existingHashes).process()
  #rss2masto("<friendly-name>", "<feed url>", conn, existingHashes).process()

  # Some examples:
  rss2masto("DARING FIREBALL", "https://daringfireball.net/feeds/main", conn, existingHashes).process()
  #rss2masto("Open Access Tracking Project", "http://tagteam.harvard.edu/remix/oatp/items.rss", conn, existingHashes).process()
  #rss2masto("CASEYLISS.COM", "https://www.caseyliss.com/rss", conn, existingHashes).process()
  #rss2masto("NYT US", "https://rss.nytimes.com/services/xml/rss/nyt/US.xml", conn, existingHashes).process() 
  #rss2masto("SIXCOLORS", "https://feedpress.me/sixcolors?type=xml", conn, existingHashes).process()
  #rss2masto("THE VERGE: APPLE", "https://www.theverge.com/apple/rss/index.xml", conn, existingHashes).process()
  #rss2masto("CNET NEWS", "https://www.cnet.com/rss/news", conn, existingHashes).process()

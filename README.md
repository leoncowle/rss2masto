# RSS2MASTO

A really simple script [rss :-)] to scrape RSS feeds and post them into a Mastodon account

If you're like me, and aren't really into using RSS Readers, but you'd still like to keep up with a handful of RSS feeds, then RSS2MASTO might be just what you're looking for. I wrote it for me, but maybe others find it useful, too.

It scrapes RSS feeds and posts them into a Mastodon account, which you can then follow with your main account. And never miss those updates again!

## Getting Started

**MASTODON PREREQS:**

I suggest creating a new Mastodon account that will be used solely to autopost into. And then you follow this new account on your main account.

In this new autoposting account, go into Settings -> Development, and choose 'New application'. Give it a name, e.g. RSS2MASTO. And untick all the Scopes. Tick (enable) the 'write:statuses' scope. That's all that's needed. Click SUBMIT.

Copy the 'Your access token' at the top (you may need to refresh the page for it to appear).

RECOMMENDATION: also in this new account's settings, go into Profile, and tick 'Require follow requests' (so no-one else can follow it without approval) and tick 'This is a bot account'.

**RSS2MASTO PREREQS:**

After cloning, edit **rss2masto.ini**, and change 'mastoHOST' to the instance of the account you want to post to.
You can optionally add the Mastodon account's access token into the ini file. Alternatively, you can put the access token into an environment variable called MASTOTOKEN. Those are the 2 ways of getting the script to know the token.

### Prerequisites

You'll need a few Python modules (which you can install into your global Python instance, or into a venv if you choose [outside the scope of this README]):

```
pip install bs4
pip install feedparser
pip install requests
```

(use pip or pip3, as needed)

## Running it

Edit rss2masto.py, and at the bottom, edit the RSS feeds you want, and/or add more. Give each a friendly name in the 1st argument.

Either manually run the script (remember to add your access token into the ini file OR into the MASTOTOKEN environment variable), or add it to cron.

**BEWARE: There is currently no file locking on the DB file (or other concurrency checks), so don't run multiple instances of the script concurrently. If you put it in cron, space them out appropriately.**

## Contributing

Pull requests are welcome.

**NOTE: This is my 1st opensource project. And I'm not a developer by profession. Be kind!**

## Authors

* **Leon Cowle** - *Initial work* - [Leon Cowle](https://github.com/leoncowle)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details


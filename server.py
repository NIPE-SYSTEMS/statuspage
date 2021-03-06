import aiohttp.web
import aiohttp_jinja2
import jinja2
import os
import sys
import yaml
import time
import datetime

class Config:
	def __init__(self):
		with open(sys.argv[1]) as f:
			self.yaml = yaml.load(f)["statuspage"]
	
	@property
	def title(self): return self.yaml.get("title", "Status")
	@property
	def token(self): return self.yaml["token"]
	@property
	def interval(self): return self.yaml.get("interval", 600)
	@property
	def groups(self): return self.yaml["groups"]
	@property
	def refresh_interval(self): return self.yaml.get("refresh_interval", 120)

class Item:
	def __init__(self, config, item):
		self.config = config
		self.name = item["name"]
		self.id = item["id"]
		self.interval = item.get("interval", self.config.interval)
		self.last_refreshed = 0 # timestamp in seconds
	
	def is_up(self):
		return time.time() <= self.last_refreshed + self.interval
	
	def refresh(self):
		self.last_refreshed = time.time()

class Group:
	def __init__(self, config, name, items):
		self.config = config
		self.name = name
		self.items = [ Item(self.config, item) for item in items ]
	
	def refresh(self, item_id):
		refreshed = 0
		for item in self.items:
			if item.id == item_id:
				item.refresh()
				refreshed += 1
		return refreshed
	
	def down_amount(self):
		return len([ 1 for item in self.items if not item.is_up() ])

class Statuspage:
	def __init__(self):
		self.config = Config()
		self.title = self.config.title
		self.token = self.config.token
		self.refresh_interval = self.config.refresh_interval
		self.groups = [ Group(self.config, name, items) for name, items in self.config.groups.items() ]
		self.app = aiohttp.web.Application()
		self.app.router.add_get("/refresh/{item_id}", self.handle_refresh)
		self.app.router.add_get("/down.png", self.handle_down_png)
		self.app.router.add_get("/up.png", self.handle_up_png)
		self.app.router.add_get("/", self.handle_main)
	
	def run(self):
		aiohttp_jinja2.setup(self.app, loader=jinja2.FileSystemLoader("."))
		aiohttp.web.run_app(self.app)
	
	async def handle_down_png(self, request):
		return aiohttp.web.FileResponse("down.png")
	
	async def handle_up_png(self, request):
		return aiohttp.web.FileResponse("up.png")
	
	@aiohttp_jinja2.template("template.html")
	async def handle_main(self, request):
		return {
			"title": self.title,
			"groups": self.groups,
			"issues": sum(self.down_amount()) > 0,
			"current_time": datetime.datetime.now().strftime("%c"),
			"refresh_interval": self.refresh_interval
		}
	
	async def handle_refresh(self, request):
		if not self.is_valid_token(request):
			return aiohttp.web.Response(status=403)
		try:
			item_id = request.match_info["item_id"]
		except KeyError:
			return aiohttp.web.Response(status=400)
		return aiohttp.web.json_response({ "refreshed": self.refresh(item_id) })
	
	def is_valid_token(self, request):
		return request.headers.get("X-Token", None) == self.token
	
	def refresh(self, item_id):
		return sum([ group.refresh(item_id) for group in self.groups ])
	
	def down_amount(self):
		return [ group.down_amount() for group in self.groups ]

Statuspage().run()

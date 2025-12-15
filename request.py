import re
import requests
import random
import urllib.parse
from bs4 import BeautifulSoup

QUIZY_URL="https://www.quizypedia.fr/get_quiz_game/"
QUIZY_IMG="https://www.quizypedia.fr/site_media/images/"

CARD_ID_RE = re.compile(r".*_card\d+$")
def getFiches(url):
	res=requests.get(url)
	if res.status_code==200:
		soup = BeautifulSoup(res.text, "html.parser")
		theme_title = soup.find("div",class_="theme_title_theme_page").text.split("(")[0].strip()
		fields=[]
		fiches=[]
		for card in soup.find_all("div", id=CARD_ID_RE):
			tables=card.find_all("tr")
			data={}
			print("\n --- New Card ---")
			print(card)
			for table in tables:
				field=table.find("td",class_="nameTd")
				if not field:
					continue
				if field.text not in fields:
					fields.append(field.text)
				data[field.text]=table.find("td",class_="valueTd").text.replace(";",",")
			img=card.find("img",class_="myImg")
			if img:
				if "Image" not in fields:
					fields.append("Image")
				data["Image"]=img["src"]
			fiches.append(data)
		return theme_title,fields,fiches
	else:
		print("Error: ",res.status_code)
		return None,None,None

def getQuizzes(session,url):
	res=session.get(url)
	if res.status_code==200:
		soup = BeautifulSoup(res.content, 'html.parser')
		lists=soup.find_all("a",attrs={"alt": "Jouer ce quiz"})
		quizzes=[liste["href"] for liste in lists]
		return quizzes
	else:
		print("Error: ",res.status_code)
		return None 

def getQuizId(session,url):
	res=session.get(url)
	soup= BeautifulSoup(res.content, 'html.parser')
	
	pattern=re.compile(r'QUIZ_ID\s*=\s*(\d+);')
	script=soup.find("script",string=pattern)
	if not script:
		return None
	matche=pattern.search(script.string)
	# check if the pattern is found
	if matche:
		return matche.group(1)
	else:
		return None

def getRandomQuiz(session):
	error=True
	while error:
		try:
			res=getQuiz(session,QUIZY_URL,random.randint(1,26822))
			error=False
		except:
			pass
	return res

def getQuiz(session,url,id):
	data={"quiz_id":f"{id}","game_mode":"quiz_chrono"}
	res=session.post(QUIZY_URL,json=data,headers={"X-Csrftoken":session.cookies["csrftoken"],"Referer":f"{url}"})
	return res.json()

def extractQuestion(quizjson):
	quiz_items=quizjson["quiz_items"]
	theme=quiz_items[0]["theme_title"]
	question=quiz_items[0]["question"]
	hints=[item["hints"] for item in quiz_items]
	responses=[item["proposed_responses"][item["response_index"]]["response"] for item in quiz_items]
	return theme,question,hints, responses

def randomQuestion(hints,responses):
	index=random.randint(0,len(hints)-1)
	return hints[index],responses[index]

def extractUrl(file):
	with open(file,"r") as f:
		text=f.read()
	link_regex = re.compile('((https?):((//)|(\\\\))+([\w\d:#@%/;$()~_?\+-=\\\.&](#!)?)*)', re.DOTALL)
	links = re.findall(link_regex, text)
	return [x[0] for x in links]

def miseenformehint(hint):
	strhint=""
	for item in hint:
		if item["type"]=="Image":
			imageurl=QUIZY_IMG+item["value"]
			imageurl=urllib.parse.quote(imageurl,safe=":/")
			strhint+=f"**{item['type']}**: [Image]({imageurl})\n"
		else:
			strhint+=f"**{item['type']}**: {item['value']}\n"
	return strhint

def miseenformeresponse(res):
	return res.split('(')[0].strip()

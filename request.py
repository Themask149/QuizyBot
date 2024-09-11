import re
import requests
import random

from bs4 import BeautifulSoup

QUIZY_URL="https://www.quizypedia.fr/get_quiz_game/"
QUIZY_IMG="https://www.quizypedia.fr/site_media/images/"
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
			strhint+=f"**{item['type']}**: [Image]({QUIZY_IMG}{item['value']})\n"
		else:
			strhint+=f"**{item['type']}**: {item['value']}\n"
	return strhint

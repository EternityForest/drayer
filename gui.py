import kivy

from kivy.app import App
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserIconView
from kivy.uix.recycleview import RecycleView




import drayer, sys, os,time
import rv

try:
	db = drayer.DrayerStream(sys.argv[1])
except:
	db = None
	




def FilePopup(x):
	layout = BoxLayout(orientation='vertical')
	fch = FileChooserIconView()
	fch.path= os.getcwd()
	button = Button(text='Post!', font_size=14, size_hint=(1,0.2))
	
	n = []
	def f():
		global db
		db= drayer.DrayerStream(fch.selection)
		n.extend(fch.selection)
		
	layout.add_widget(fch)
	layout.add_widget(button)
	
	popup = Popup(title='Test popup', content=layout, size_hint=(None, None), size=(600, 400))

	button.bind(on_press=popup.dismiss)
	popup.open()

def getPublicSocialposts():
	c = db.getConn().cursor()
	c.execute('SELECT key,value FROM record WHERE key LIKE "PublicSocialPost%"')
	return c


def rl():
	pass
	

rlfun = rl

class MyApp(App):

	def build(self):
		layout = BoxLayout(orientation='vertical')
		body = BoxLayout(orientation='horizontal')

		c1 = BoxLayout(orientation='vertical')
		c2 = BoxLayout(orientation='vertical')
		sel = Button(text='Select a File', font_size=14, size_hint=(1,0.1))
		layout.add_widget(sel)
		layout.add_widget(body)

			
		body.add_widget(c1)
		body.add_widget(c2)
		
	

		newpost = TextInput()
		submit = Button(text='Post!', font_size=14, size_hint=(1,0.2))
				
		c1.add_widget(newpost)
		c1.add_widget(submit)
		
		allposts = rv.RV()

		c2.add_widget(allposts)
		
		def rf():
			d = []
			for i in getPublicSocialposts():
				k=i["key"].split("_",2)
				t = 12345
				try:
					t = float(k[1])
					title=k[2]
				except:
					title="Untitled"
				d.append({"text":time.strftime("%Y %b %d %I:%M%p",time.gmtime(t))+"\n"+title})
			allposts.data = d
			
		allposts.data=[{"text":"foo"}, {"text":"bar"}]
		rf()

		
		def post(instance):
			db["PublicSocialPost_"+str(time.time())+"_title"] = newpost.text

		submit.bind(on_press=post)
		sel.bind(on_press=FilePopup)
		
		return layout


if __name__ == '__main__':
    MyApp().run()

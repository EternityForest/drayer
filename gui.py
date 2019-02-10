import kivy

from kivy.app import App
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserIconView


import drayer, sys, os,time

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

class MyApp(App):

	def build(self):
		layout = BoxLayout(orientation='vertical')
		
		sel = Button(text='Select a File', font_size=14, size_hint=(1,0.1))

		newpost = TextInput()
		button = Button(text='Post!', font_size=14, size_hint=(1,0.2))
		
		layout.add_widget(sel)

		layout.add_widget(newpost)
		layout.add_widget(button)
		
		def post(instance):
			db["PublicSocialPost_"+str(time.time())] = newpost.text

		button.bind(on_press=post)
		sel.bind(on_press=FilePopup)
		
		return layout


if __name__ == '__main__':
    MyApp().run()

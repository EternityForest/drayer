import traceback,os
import kivy
import base64

from kivy.config import Config
Config.set('graphics', 'show_cursor', '1')

from kivy.app import App
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.recycleview import RecycleView
from kivy.lang import Builder

Builder.load_string('''
<RecycleView, Label, Button>
    
    font_size: 18
    canvas.before:
        Color:
            rgba: 0.8, 0.8, 0.8, 1
        Rectangle:
            pos: self.pos
            size: self.size
    
    canvas.after:
        Color:
            rgba: 0.55, 0.65, 0.4, 1
        Line:
            points: [self.pos[0],self.pos[1]+1,   self.pos[0]+self.size[0]-1,self.pos[1],     self.pos[0]+self.size[0]-1, self.pos[1]+self.size[1]+1 ]
            width: dp(2)

        Color:
            rgba: 0.35, 0.45, 0.3, 1
        Line:
            points: [self.pos[0],self.pos[1],   self.pos[0],self.pos[1]+self.size[1],     self.pos[0]+self.size[0], self.pos[1]+self.size[1] ]
            width: dp(3)


        Color:
            rgba: 0.1, 0.2, 0.08, 1
        Line:
            points: [self.pos[0]+dp(2),self.pos[1],   self.pos[0]+dp(2),self.pos[1]+self.size[1]-dp(2),     self.pos[0]+self.size[0]+dp(2), self.pos[1]+self.size[1]-dp(2) ]
            width: dp(2)

[FileListEntry@FloatLayout+TreeViewNode]:
    locked: False
    entries: []
    path: ctx.path
    # FIXME: is_selected is actually a read_only treeview property. In this
    # case, however, we're doing this because treeview only has single-selection
    # hardcoded in it. The fix to this would be to update treeview to allow
    ## multiple selection.nam
    is_selected: self.path in ctx.controller().selection

    orientation: 'horizontal'
    size_hint_y: None
    height: '48dp' if dp(1) > 1 else '24dp'
    # Don't allow expansion of the ../ node
    is_leaf: not ctx.isdir or ctx.name.endswith('..' + ctx.sep) or self.locked
    on_touch_down: self.collide_point(*args[1].pos) and ctx.controller().entry_touched(self, args[1])
    on_touch_up: self.collide_point(*args[1].pos) and ctx.controller().entry_released(self, args[1])
    BoxLayout:
        pos: root.pos
        size_hint_x: None
        width: root.width - dp(10)
        Label:
            canvas.before:
                Color:
                    rgba: 0.8, 0.8, 0.8, 1
                Rectangle:
                    pos: self.pos
                    size: self.size
            # --------------
            # CHANGE FONT COLOR
            # --------------
            color: 0, 0, 0, 1
            id: filename
            text_size: self.width, None
            halign: 'left'
            shorten: True
            text: ctx.name

''')



import drayer, sys, os,time
import rv

db = None

#The UI redefines this. It's the callback for what drayer should
#call to refresh the UI
def rl():
    pass
rlfun = rl

class DrayerRefresher(drayer.DrayerStream):
    def onChange(self, op, x,y,z):
        rlfun()


drayer.startServer()
drayer.startLocalDiscovery()

import atexit

def cleanup():
    db.close()
atexit.register(cleanup)

def openStream(x,pk=None):
    global db
    if(db):
        db.close()
    db = DrayerRefresher(x,pk)
    rlfun()



def presentError(x=None):
    x=x or traceback.format_exc()
    layout = BoxLayout(orientation='vertical')
    
    yes = Button(text='Ok', font_size=18, size_hint=(1,0.1))

        
    layout.add_widget(TextInput(text=x))
    layout.add_widget(yes)

    popup = Popup(title='Error', content=layout, size_hint=(None, None), size=(600, 400))

    def y(*a,**k):
        popup.dismiss()

    yes.bind(on_press=y)
    popup.open()


try:
    openStream(sys.argv[1])
    print("Opened "+sys.argv[1])
except:
    print(traceback.format_exc())
    presentError(traceback.format_exc())
    db = None
    






def FilePopup(x):
    layout = BoxLayout(orientation='vertical')


    fch = FileChooserListView()
    fch.path= os.getcwd()

    pubkey = TextInput(hint_text="Public Key of the stream, leave blank to create new stream or accept the one in the file", multiline=False,size_hint=(1,0.1))
    filename = TextInput(hint_text="Filename", multiline=False,size_hint=(1,0.1))

    button = Button(text='Select', font_size=14, size_hint=(1,0.1))

    def s(x,y):
        try:
            filename.text = os.path.basename(str(fch.selection[0]))
        except:
            filename.text =''
    fch.bind(selection=s)
    n = []

    def f(j):
        try:
            if filename.text:
                openStream(os.path.join(fch.path,filename.text) ,pubkey.text)
                n.extend(fch.selection)
            else:
                presentError("Nothing selected!s")
        except:
            presentError(traceback.format_exc())
        popup.dismiss()

    layout.add_widget(pubkey)
    layout.add_widget(fch)
    layout.add_widget(filename)

    layout.add_widget(button)
    
    popup = Popup(title='Open or Create a Stream', content=layout, size_hint=(None, None), size=(600, 400))

    button.bind(on_press=f)

    popup.open()

def ConfirmPopup(x, cb):
    layout = BoxLayout(orientation='vertical')
    
    yes = Button(text='Confirm', font_size=14, size_hint=(1,0.2))
    no = Button(text='Cancel', font_size=14, size_hint=(1,0.2))

        
    layout.add_widget(Label(text=x))
    layout.add_widget(yes)
    layout.add_widget(no)

    popup = Popup(title='Confirm?', content=layout, size_hint=(None, None), size=(600, 400))

    def y(*a,**k):
        cb(True)
        popup.dismiss()
    def n(*a,**k):
        cb(False)
        popup.dismiss()

    yes.bind(on_press=y)
    no.bind(on_press=n)
    popup.open()


def PubkeyPopup(x):
    layout = BoxLayout(orientation='vertical')
    yes = Button(text='Ok', font_size=18, size_hint=(1,0.2))

        
    layout.add_widget(TextInput(text=x))
    layout.add_widget(yes)

    popup = Popup(title='Confirm?', content=layout, size_hint=(None, None), size=(600, 400))

    def y(*a,**k):
        popup.dismiss()

    yes.bind(on_press=y)
    popup.open()



def getPublicSocialposts():
    c = db.getConn().cursor()
    c.execute('SELECT key,value FROM record WHERE key LIKE "PublicSocialPost%" ORDER BY id desc')
    return c

def getOneSocialPost(key):
    d=db[key]
    k=key.split("_",2)
    t = 12345
    try:
        t = float(k[1])
        title=k[2]
    except:
        title="Untitled"
    return (title, t, d)

class MyApp(App):

    def build(self):
        layout = BoxLayout(orientation='vertical')
        body = BoxLayout(orientation='horizontal')

        buttonbar=BoxLayout(orientation="horizontal",size_hint=(1,0.05))

        c1 = BoxLayout(orientation='vertical')
        c2 = BoxLayout(orientation='vertical')
        sel = Button(text='Select a File', font_size=14, size_hint=(0.3,1))
        showpubkey = Button(text='Show the pubkey', font_size=14, size_hint=(0.3,1))
        sync = Button(text='Sync!', font_size=14, size_hint=(0.3,1))


        buttonbar.add_widget(showpubkey)
        buttonbar.add_widget(sel)
        buttonbar.add_widget(sync)

        layout.add_widget(buttonbar)
        layout.add_widget(body)

            
        body.add_widget(c1)
        body.add_widget(c2)
        
        #
        newposttitle = TextInput(hint_text="Title", multiline=False,size_hint=(1,0.1))

        #Edit the selected post
        newpost = TextInput()
        submit = Button(text='Update!', font_size=14, size_hint=(1,0.1))
        
        c1.add_widget(newposttitle)
        c1.add_widget(newpost)
        c1.add_widget(submit)
        
        allposts = rv.RV()
        allposts.selected="newpost"
        c2.add_widget(allposts)


        delb = Button(text='Delete Selected', font_size=14, size_hint=(1,0.1))
        c2.add_widget(delb)


        global rlfun
        def rf():
            if db:
                try:
                    d = [{"text":"Create New Post", "value":"newpost"}]
                    for i in getPublicSocialposts():
                        k=i["key"].split("_",2)
                        t = 12345
                        try:
                            t = float(k[1])
                            title=k[2]
                        except:
                            title="Untitled"
                        d.append({"text":time.strftime("%Y %b %d %I:%M%p",time.gmtime(t))+" "+title,"value":i['key']})
                    allposts.data = d
                except:
                    presentError()
            
        allposts.data=[{"text":"foo"}, {"text":"bar"}]
        rlfun = rf
        rf()

        oldsel = [newpost]

        def dels(c):
            if allposts.selected=="newpost":
                return
            
            #Copy, so it doesn't get changed before they click
            x = allposts.selected
            def f(y):
                if y:
                    try:
                        del db[allposts.selected]
                        rf()
                    except:
                        presentError(traceback.format_exc())
            ConfirmPopup("Really delete "+newposttitle.text+"?", f)
        delb.bind(on_press=dels)

        def onSelect(post):
            if post=="newpost":
                newposttitle.readonly = False
                if not oldsel[0]==post:
                    newposttitle.text=''
                    newpost.text=''
            else:
                newposttitle.readonly=True
                try:
                    p = getOneSocialPost(post)
                    newposttitle.text = p[0]
                    newpost.text= p[2]
                except:
                    presentError()
               
            oldsel[0] = newpost

        allposts.onSelect= onSelect

        def post(instance):
            if allposts.selected=="newpost":
                db["PublicSocialPost_"+str(time.time())+"_"+newposttitle.text] = newpost.text
                newpost.text = ''
                newposttitle.text =''
                rf()
            else:
                db[allposts.selected]=newpost.text
        
        def spk(inst):
            if db:
                PubkeyPopup(base64.b64encode(db.pubkey))
            else:
                presentError("No stream loaded!")

        def sf(inst):
            if db:
               db.sync()
            else:
                presentError("No stream loaded!")  
        sync.bind(on_press=sf)    
        showpubkey.bind(on_press=spk)
        submit.bind(on_press=post)
        sel.bind(on_press=FilePopup)
        
        return layout


if __name__ == '__main__':
    MyApp().run()

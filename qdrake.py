#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
ZetCode PyQt5 tutorial 

In this example, we create a simple
window in PyQt5.

Author: Jan Bodnar
Website: zetcode.com 
Last edited: August 2017
"""

import sys
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *



import drayer, sys, os,time
import rv

db = None

#The UI redefines this. It's the callback for what drayer should
#call to refresh the UI
def rl():
    pass
rlfun = rl



drayer.startServer()
drayer.startLocalDiscovery()

import atexit

def cleanup():
    db.close()
atexit.register(cleanup)

def getPublicSocialposts(stream):
    c = stream.getConn().cursor()
    c.execute('SELECT key,value FROM record WHERE type="publicSocialPost" ORDER BY id desc')
    return c

def errorWindow(e=None):
    jhj

def getOneSocialPost(key,stream):
    d=stream.rawGetItemByKey(key,'publicSocialPost')
    k=key.split(":",1)
    t = 12345
    try:
        t = float(k[0])
        title=k[1]
    except:
        title="Untitled"
    return (title, t, d)



class DrayerRefresher(drayer.DrayerStream):
    def onChange(self, op, x,y,z):
        self.parent.onChange()

class DrayerStreamTab(QWidget):
    def __init__(self,fn,pk=None):
        QWidget.__init__(self)
        self.stream = DrayerRefresher(fn,pk)
        self.stream.parent=self

        self.lo= QHBoxLayout()
        self.setLayout(self.lo)

        self.lo.addWidget(self._leftColumn())
        self.lo.addWidget(self._rightColumn())
        self.titleToKey = {}
        self.reloadAll()

    def reloadAll(self):
        self.reloadList()

    def reloadList(self):
        for i in getPublicSocialposts(self.stream):
            k=i["key"].split(":",1)
            t = 12345
            try:
                t = float(k[0])
                title=k[1]
            except:
                title="Untitled"
            title = time.strftime("%Y %b %d %I:%M%p",time.gmtime(t))+" "+title
            x = QListWidgetItem()
            x.k = i['key']

            x.setText(title)
            self.streamContents.addItem(x)

    
    def _leftColumn(self):
        lw = QWidget()
        l = QVBoxLayout()
        lw.setLayout(l)

        self.titlebox = QLineEdit() 
        l.addWidget(self.titlebox)

        self.textbox = QTextEdit()
        l.addWidget(self.textbox)

        self.updateButton = QPushButton("Update")
        l.addWidget(self.updateButton)
        return lw

    def _onSelectPosting(self,*args):
        try:
            s = self.streamContents.selectedItems()[0].k
            p = getOneSocialPost(s, self.stream)
            self.textbox.setText(p[2].decode("utf8"))
        except:
            errorWindow()

    def _rightColumn(self):
        lw = QWidget()
        l = QVBoxLayout()
        lw.setLayout(l)

        self.streamContents = QListWidget()
        self.streamContents.itemSelectionChanged.connect(self._onSelectPosting)
        l.addWidget(self.streamContents)
        return lw


class Window(QMainWindow):

    def __init__(self):
        super(Window, self).__init__()
        self.setGeometry(50, 50, 500, 300)
        self.setWindowTitle("PyQT tuts!")
        self.setWindowIcon(QIcon('pythonlogo.png'))

        extractAction = QAction("&GET TO THE CHOPPAH!!!", self)
        extractAction.setShortcut("Ctrl+Q")
        extractAction.setStatusTip('Leave The App')
       # extractAction.triggered.connect(self.close_application)

        mainMenu = self.menuBar()
        fileMenu = mainMenu.addMenu('&File')
        fileMenu.addAction(extractAction)
        
    
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.tabs.addTab(DrayerStreamTab("/home/daniel/drayer/fooo.stream"),"opopopo")

def run():
    app = QApplication(sys.argv)
    GUI = Window()
    GUI.show()
    sys.exit(app.exec_())
    
if __name__ == '__main__':
    
    run()
    sys.exit(app.exec_())
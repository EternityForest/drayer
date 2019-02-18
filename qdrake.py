#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import QObject, pyqtSignal




import drayer, sys, os,time
import webbrowser,urllib, base64

dracoStyle="""
    QWidget{
        background-color: rgb(220,240,200);
        border-color: rgb(89,60,7);
        border-width: 3px;
        selection-background-color: rgb(200,150,120);
        selection-color: rgb(255,255,230);


    }
    QTextEdit,QLineEdit,QListWidget
    {
        background-color: rgb(240,255,230);
    }
    QPushButton
    {
        background-color: rgb(200,150,120)
    }

"""

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

def getFiles(stream):
    c = stream.getConn().cursor()
    c.execute('SELECT key,value FROM record WHERE type="file" ORDER BY key asc')
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




class DrayerRefresher(QObject, drayer.DrayerStream):

    ch = pyqtSignal()
    def __init__(self, *a,**k):
        QObject.__init__(self)
        drayer.DrayerStream.__init__(self,*a,**k)

    def onChange(self, op, x,y,z):
        self.ch.emit()

import socket
#https://stackoverflow.com/questions/166506/finding-local-ip-addresses-using-pythons-stdlib
def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

class DrayerStreamTab(QWidget):

    def url(self,domain="localhost"):
        return ("http://"+ domain+":"+str(drayer.http_port)+"/webAccess/"+
        urllib.parse.quote_plus(base64.b64encode(self.stream.pubkey).decode("utf8"))+"/"+"index.html")

    def showQR(self):
        from PIL.ImageQt import ImageQt
        import qrcode
     
        laddr = str(get_ip())
        qim = ImageQt(qrcode.make(self.url(laddr)))
        pix = QPixmap.fromImage(qim)

        d = QDialog(self)
        l=QLabel(d)
        l.setFixedSize(480,480)

        l.setPixmap(pix)
        d.adjustSize()
        d.show() 

    def showFilesDialog(self):
        d = QDialog(self)
        w=QWidget(d)
        lo=QVBoxLayout()
        w.setLayout(lo)

        l = QListWidget()
        lo.addWidget(l)

        for i in getFiles(self.stream):
            j = QListWidgetItem()
            j.setText(i["key"])
            l.addItem(j)

        d.adjustSize()
        d.show() 

    def showPubkey(self):

        d = QDialog(self)
        l=QTextEdit(d)
    
        l.setText("Filename:\r\n"+self.stream.fn+"\r\n\r\nPublic Key(Base64):\r\n"+
            base64.b64encode(self.stream.pubkey).decode("utf8")+"\r\n\r\nPubkey(PGP encoded):\r\n"+self.stream.pgpFingerprint())
        l.setFixedSize(480,240)
        l.setReadOnly(True)
        d.adjustSize()
        d.show() 

    def __init__(self,fn,pk=None):
        QWidget.__init__(self)
        self.stream = DrayerRefresher(fn,pk)
        self.stream.ch.connect(self.onChange)


        self.lo= QHBoxLayout()
        self.setLayout(self.lo)

        self.lo.addWidget(self._leftColumn())
        self.lo.addWidget(self._rightColumn())
        self.titleToKey = {}
        self.reloadAll()
        self.selectedPost = "newpost"

    def onChange(self):
        self.reloadAll()

    def reloadAll(self):
        self.reloadList()

    def reloadList(self):
        self.streamContents.clear()

        x = QListWidgetItem()
        x.k="newpost"
        x.setText("New Post")
        self.streamContents.addItem(x)
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

    def updatePost(self,*args):

        if self.selectedPost=="newpost":
            if not self.titlebox.text():
                errorWindow("Empty title!")
                return
            self.stream.rawSetItem(str(time.time())+":"+self.titlebox.text(),self.textbox.toPlainText().encode("utf8"),"publicSocialPost")
            self.titlebox.setText('')
            self.textbox.setText('')
        else:
            self.stream.rawSetItem(self.selectedPost, self.textbox.toPlainText().encode("utf8"),"publicSocialPost")
            self.reloadList()

    def deletePrompt(self):
        s = self.streamContents.selectedItems()[0]

        t = s.text()
        k=s.k
        buttonReply = QMessageBox.question(self, 'Really delete?', "Delete "+t, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if buttonReply==QMessageBox.Yes:
            self.stream.rawDelete(k,"publicSocialPost")


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

        self.updateButton.clicked.connect(self.updatePost)
        return lw

    def _onSelectPosting(self,*args):
        if not self.streamContents.selectedItems():
            self.selectedPost="newpost"
            self.delbt.setDisabled(True)
            self.titlebox.setText('')
            self.textbox.setText('')
            return
        try:
            s = self.streamContents.selectedItems()[0].k
            if s=="newpost":
                self.titlebox.setText('')
                self.textbox.setText('')
                self.selectedPost= s
                self.titlebox.setReadOnly(False)
                self.delbt.setDisabled(True)
            else:
                self.titlebox.setReadOnly(True)
                self.selectedPost= s
                p = getOneSocialPost(s, self.stream)
                self.textbox.setText(p[2].decode("utf8"))
                self.titlebox.setText(p[0])
                self.delbt.setDisabled(False)

        except:
            errorWindow()

    def syncButtonF(self):
        self.stream.sync()

    def _rightColumn(self):
        lw = QWidget()
        l = QVBoxLayout()
        lw.setLayout(l)

        self.syncButton = QPushButton("Sync!")

        self.streamContents = QListWidget()
        self.streamContents.itemSelectionChanged.connect(self._onSelectPosting)

        self.delbt= QPushButton("Delete Selected")
        self.delbt.clicked.connect(self.deletePrompt)
        self.delbt.setDisabled(True)
        self.syncButton.clicked.connect(self.syncButtonF)
        l.addWidget(self.syncButton)
        l.addWidget(self.streamContents)
        l.addWidget(self.delbt)

        return lw


class Window(QMainWindow):

    def loadWizard(self):
        fn = QFileDialog.getOpenFileName(self,"Select stream", os.getcwd(), "Streams (*.drayer *.stream)")
        self.tabs.addTab(DrayerStreamTab(fn[0]),os.path.basename(fn[0]))


    def deletePrompt():
        self.tabs.currentWidget().deletePrompt()

    def qr(self):
        self.tabs.currentWidget().showQR()

    def showFiles(self):
        self.tabs.currentWidget().showFilesDialog()
    
    def showPubkey(self):
        self.tabs.currentWidget().showPubkey()

    def createWizard(self):
        pk = QInputDialog.getText(self, "Enter Public Key of the Stream","Leave blank to create a new stream with a new keypair in publish mode" )

        fn = QFileDialog.getSaveFileName(self,"Select stream", os.getcwd(), "Streams (*.drayer *.stream)")
        self.tabs.addTab(DrayerStreamTab(fn[0],pk[0]),os.path.basename(fn[0]))

    def syncFilesPrompt(self):
        db = self.tabs.currentWidget().stream
        fn = QFileDialog.getExistingDirectory(self,"Select Folder to Sync With", os.getcwd())
        db.importFiles(fn,True)

    def runBrowser(self):
        db = self.tabs.currentWidget().stream
        webbrowser.open(db.url())
    
    
    def __init__(self):
        super(Window, self).__init__()
        self.setGeometry(50, 50, 500, 300)
        self.setWindowTitle("Drake")
        self.setWindowIcon(QIcon('swamp_dragon_new.png'))

        loadAction = QAction("&Load stream", self)
        loadAction.setStatusTip('Load an existing streamfile')
        loadAction.triggered.connect(self.loadWizard)

        createAction = QAction("&Create or Import a stream", self)
        createAction.triggered.connect(self.createWizard)

        browserAction = QAction("&View stream files in web browser", self)
        browserAction.setStatusTip("Opens the stream's index.html")
        browserAction.triggered.connect(self.runBrowser)

        qrAction = QAction("&QR For mobile browser", self)
        qrAction.triggered.connect(self.qr)

        filesAction = QAction("&Show files in stream", self)
        filesAction.triggered.connect(self.showFiles)

        keyAction = QAction("&Show public key", self)
        keyAction.triggered.connect(self.showPubkey)


        importAction = QAction("&Sync with folder", self)
        importAction.setStatusTip("Add files in folder to stream, remove files not in folder")
        importAction.triggered.connect(self.syncFilesPrompt)

        mainMenu = self.menuBar()
        fileMenu = mainMenu.addMenu('&File')
        actionMenu = mainMenu.addMenu('&Action')

        fileMenu.addAction(loadAction)
        fileMenu.addAction(createAction)
        fileMenu.addAction(filesAction)
        fileMenu.addAction(keyAction)

        actionMenu.addAction(browserAction)
        actionMenu.addAction(importAction)
        actionMenu.addAction(qrAction)
    
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

def run():
    app = QApplication(sys.argv)
    app.setStyleSheet(dracoStyle)

    GUI = Window()
    GUI.show()
    sys.exit(app.exec_())
    
if __name__ == '__main__':
    
    run()
    sys.exit(app.exec_())
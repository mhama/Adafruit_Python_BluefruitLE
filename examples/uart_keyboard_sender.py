#!/usr/bin/python
# transfer BLE UART key press command to USB HID
# requirement: PyQt5
# Modified by Makoto Hamanaka
# Original Author: Tony DiCola
import Adafruit_BluefruitLE
from Adafruit_BluefruitLE.services import UART

from PyObjCTools import AppHelper
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtCore import Qt
import threading
import traceback

# refs:
# * usb_hid_keys.h
#   https://gist.github.com/MightyPork/6da26e382a7ad91b5496ee55fdc73db2
# * Mac OS virtual key code
#   https://monobook.org/wiki/%E3%82%AD%E3%83%BC%E3%82%B3%E3%83%BC%E3%83%89/Mac_OS_X
# * PyQt5 QtKeyEvent
#   https://doc.qt.io/qt-5/qkeyevent.html
class KeyCodeConverter:
    MOD_ANYKEY = 0x100
    MOD_CMD = 0x100000
    MOD_SHIFT = 0x20000
    MOD_LSHIFT = 0x2
    MOD_RSHIFT = 0x4
    MOD_CTRL = 0x40000
    MOD_LCTRL = 0x1
    MOD_RCTRL = 0x2000
    MOD_OPT = 0x80000
    MOD_LOPT = 0x20
    MOD_ROPT = 0x40

    HID_MOD_LCTRL  = 0x01
    HID_MOD_LSHIFT = 0x02
    HID_MOD_LALT   = 0x04
    HID_MOD_LMETA  = 0x08 # Command key
    HID_MOD_RCTRL  = 0x10
    HID_MOD_RSHIFT = 0x20
    HID_MOD_RALT   = 0x40
    HID_MOD_RMETA  = 0x80 # Command key

    vkeyCodeToHidKeyTable = [
        # 0-  a,s,d,f,h,g,z,x,c,v, none,b,q,w
        0x04, 0x16, 0x07, 0x09, 0x0b, 0x0a, 0x1d, 0x1b, 0x06, 0x19, 0, 0x05, 0x14, 0x1a,
        # 14- e,r,y,t,1,2,3,4,6,5,+,9,7
        0x08, 0x15, 0x1c, 0x17, 0x1e, 0x1f, 0x20, 0x21, 0x23, 0x22, 0x2e, 0x26, 0x24,
        # 27- -, 8, 0, ], o, u, [, i, p, enter(win keyboard), l, j
        0x2d, 0x25, 0x27, 0x30, 0x12, 0x18, 0x2f, 0x0c, 0x13, 0x28, 0x0f, 0x0d,
        # 39- ', k, ;, \, ',' , /, n, m, ., tab, space, none, BS, return(mac), esc(=53)
        0x34, 0x0e, 0x33, 0x31, 0x36, 0x38, 0x11, 0x10, 0x37, 0x2b, 0x2c, 0, 0x2a, 0x28, 0x29,
    ]

    vkeyCodeToHidKeyDic = {
            93: 0x31, # \ and |
            117: 0x4c, # delete
            123: 0x50, # left-arrow
            124: 0x4f, # right-arrow
            125: 0x51, # down-arrow
            126: 0x52, # up-arrow
            }

    def __init__(self, event):
        self.event = event
        self.key = event.key()
        self.vkey = event.nativeVirtualKey()
        self.scan = event.nativeScanCode()
        self.mod = event.nativeModifiers()
        self.hidMod = self.makeHidModBits(self.mod)
        self.hidKey = self.convertToHidKey(self.vkey)
        self.isKey = True if (self.mod & self.MOD_ANYKEY) else False

#    def hidMod(self):
#        return self.hidMod
#
#    def hidKey(Self):
#        return self.hidKey
#
#    def isKey(self):
#        return self.isKey

    def convertToHidKey(self, vkey):
        print("vkey:"+str(vkey))
        if vkey < len(self.vkeyCodeToHidKeyTable):
            return self.vkeyCodeToHidKeyTable[vkey]
        if vkey in self.vkeyCodeToHidKeyDic:
            return self.vkeyCodeToHidKeyDic[vkey]
        return 0

    def makeHidModBits(self, mod):
        return self.makeHidModBit(mod, self.MOD_LSHIFT, self.HID_MOD_LSHIFT) | \
               self.makeHidModBit(mod, self.MOD_RSHIFT, self.HID_MOD_RSHIFT) | \
               self.makeHidModBit(mod, self.MOD_LOPT,   self.HID_MOD_LALT) | \
               self.makeHidModBit(mod, self.MOD_ROPT,   self.HID_MOD_RALT) | \
               self.makeHidModBit(mod, self.MOD_CMD,    self.HID_MOD_LMETA) | \
               self.makeHidModBit(mod, self.MOD_LCTRL,  self.HID_MOD_LCTRL) | \
               self.makeHidModBit(mod, self.MOD_RCTRL,  self.HID_MOD_RCTRL)

    def makeHidModBit(self, mod, macModBit, hidModBit):
        return hidModBit if (mod & macModBit) else 0

class App(QWidget):

    def __init__(self):
        QWidget.__init__(self)
        self.title = 'Macbook as Keyboard'
        self.left = 10
        self.top = 10
        self.width = 320
        self.height = 200
        self.initUI()
        self.sender = UartSender()
        self.sender.connectAsync(self.onConnect)
        #self.keyCodeTable="asdfhgzxcv bqweryt123465+97-80]ou[ip lj'k;\\,/nm."

    def keyPressEvent(self, event):
        key = event.key()
        vkey = event.nativeVirtualKey()
        scan = event.nativeScanCode()
        mod = event.nativeModifiers()
        #msg = "vkey-mac:"+str(vkey)+","+hex(mod)+","+str(scan)
        conv = KeyCodeConverter(event)
        #msg = self.usbHidKeyMsg(event)
        #print("sending "+msg)
        #self.sender.sendAsync(msg)
        if conv.isKey:
          msg = "hidPress:"+hex(conv.hidKey)+","+hex(conv.hidMod)
          print("converted "+msg)
          self.sender.sendAsync(msg)

        # keycode: https://qiita.com/baba163/items/e2390c4529ec0448151d
        #if key == Qt.Key_Escape:
        #    print('esc')

    def onConnect(self, success):
        print("connection finished:"+str(success))

    def initUI(self):
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)
        
        button = QPushButton('Focus this window to send keys', self)
        button.setToolTip('This is an example button')
        button.move(100,70)
        button.clicked.connect(self.on_click)
        
        self.show()

    @pyqtSlot()
    def on_click(self):
        print('PyQt5 button click')
        self.sender.sendAsync("heee")

# Get the BLE provider for the current platform.
ble = Adafruit_BluefruitLE.get_provider()


# Main function implements the program logic so it can run in a background
# thread.  Most platforms require the main thread to handle GUI events and other
# asyncronous events like BLE actions.  All of the threading logic is taken care
# of automatically though and you just need to provide a main function that uses
# the BLE provider.

class UartSender:
    def __init__(self):
        print("UartSender")
        self.uart = None
        self.device = None

    def isReadyToSend(self):
        return (self.uart != None)

    def connectAsync(self, onFinished):
        thread = threading.Thread(target=self.connect, args=(onFinished,))
        thread.start()

    def connect(self, onFinished):
        # Clear any cached data because both bluez and CoreBluetooth have issues with
        # caching data and it going stale.
        ble.clear_cached_data()
    
        # Get the first available BLE network adapter and make sure it's powered on.
        adapter = ble.get_default_adapter()
        adapter.power_on()
        print('Using adapter: {0}'.format(adapter.name))
    
        # Disconnect any currently connected UART devices.  Good for cleaning up and
        # starting from a fresh state.
        print('Disconnecting any connected UART devices...')
        UART.disconnect_devices()
    
        # Scan for UART devices.
        print('Searching for UART device...')
        try:
            adapter.start_scan()
            # Search for the first UART device found (will time out after 60 seconds
            # but you can specify an optional timeout_sec parameter to change it).
            self.device = UART.find_device()
            if self.device is None:
                raise RuntimeError('Failed to find UART device!')
        finally:
            # Make sure scanning is stopped before exiting.
            adapter.stop_scan()
    
        print('Connecting to device...')
        self.device.connect()  # Will time out after 60 seconds, specify timeout_sec parameter
                          # to change the timeout.
    
        # Once connected do everything else in a try/finally to make sure the device
        # is disconnected when done.
        success = False
        try:
            # Wait for service discovery to complete for the UART service.  Will
            # time out after 60 seconds (specify timeout_sec parameter to override).
            print('Discovering services...')
            UART.discover(self.device)
    
            # Once service discovery is complete create an instance of the service
            # and start interacting with it.
            self.uart = UART(self.device)
            success = True
        except:
            traceback.print_exc()
            self.device.disconnect()
            self.device = None
            self.uart = None
        finally:
            # Make sure device is disconnected on exit.:
            onFinished(success)

    def sendAsync(self, msg):
        thread = threading.Thread(target=self.send, args=(msg,))
        thread.start()

    def send(self, msg):
        try:
            # Write a string to the TX characteristic.
            cmd = msg
            self.uart.write(cmd.encode())
            print("Sent "+msg+" to the device.")
        except:
            traceback.print_exc()

    def recv(self):
        try:
            # Now wait up to one minute to receive data from the device.
            print('Waiting up to 60 seconds to receive data from the device...')
            received = self.uart.read(timeout_sec=1)
            if received is not None:
                # Received data, print it out.
                print('Received: {0}'.format(received))
            else:
                # Timeout waiting for data, None is returned.
                print('Received no data!')
        except:
            traceback.print_exc()


    def close():
        self.device.disconnect()



# Initialize the BLE system.  MUST be called before other BLE calls!
ble.initialize()

# Start the mainloop to process BLE events, and run the provided function in
# a background thread.  When the provided main function stops running, returns
# an integer status code, or throws an error the program will exit.
#ble.run_mainloop_with(main)


app = QApplication(sys.argv)
ex = App()
sys.exit(app.exec_())


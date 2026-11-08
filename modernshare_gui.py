#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""ModernShare updater-to-firmware GUI for Windows and Linux (Tkinter)."""
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog,messagebox,ttk
import webbrowser

from modernshare_patcher import DOWNLOAD_PAGE,generate

class App:
    def __init__(self,root):
        self.root=root;self.busy=False;self.events=queue.Queue()
        root.title('ModernShare firmware builder');root.geometry('740x540');root.minsize(710,540)
        self.source=tk.StringVar();self.folder=tk.StringVar();self.status=tk.StringVar(value='Select the Kodak updater to get started.')
        style=ttk.Style(root)
        if 'clam' in style.theme_names():style.theme_use('clam')
        style.configure('TFrame',background='#fff4e7')
        style.configure('TLabel',background='#fff4e7',foreground='#30241e')
        style.configure('Title.TLabel',font=('TkDefaultFont',25,'bold'),foreground='#c54c13')
        style.configure('Section.TLabel',font=('TkDefaultFont',11,'bold'))
        style.configure('Accent.TButton',padding=(18,10),background='#d95718',foreground='white')
        style.map('Accent.TButton',background=[('active','#bf4510'),('disabled','#e6b59a')])
        page=ttk.Frame(root,padding=26);page.pack(fill='both',expand=True);page.columnconfigure(0,weight=1)
        ttk.Label(page,text='ModernShare',style='Title.TLabel').grid(row=0,column=0,sticky='w')
        ttk.Label(page,text='Firmware builder · version 0.8 · Kodak CD703 / C713 1.30').grid(row=1,column=0,sticky='w',pady=(2,22))
        ttk.Label(page,text='1. Select the Kodak updater',style='Section.TLabel').grid(row=2,column=0,sticky='w')
        inputs=ttk.Frame(page);inputs.grid(row=3,column=0,sticky='ew',pady=(8,5));inputs.columnconfigure(0,weight=1)
        ttk.Entry(inputs,textvariable=self.source,state='readonly').grid(row=0,column=0,sticky='ew',padx=(0,8))
        self.browse=ttk.Button(inputs,text='Browse…',command=self.select_source);self.browse.grid(row=0,column=1)
        ttk.Label(page,text='Choose KC713130.exe. The app reads the archive without running it.').grid(row=4,column=0,sticky='w')
        self.download=ttk.Button(page,text='Open firmware download page ↗',command=lambda:webbrowser.open(DOWNLOAD_PAGE))
        self.download.grid(row=5,column=0,sticky='w',pady=(7,20))
        ttk.Label(page,text='2. Choose where to save KC713.FW',style='Section.TLabel').grid(row=6,column=0,sticky='w')
        outputs=ttk.Frame(page);outputs.grid(row=7,column=0,sticky='ew',pady=(8,18));outputs.columnconfigure(0,weight=1)
        ttk.Entry(outputs,textvariable=self.folder,state='readonly').grid(row=0,column=0,sticky='ew',padx=(0,8))
        self.choose=ttk.Button(outputs,text='Choose folder…',command=self.select_folder);self.choose.grid(row=0,column=1)
        self.button=ttk.Button(page,text='Generate firmware',style='Accent.TButton',command=self.start)
        self.button.grid(row=8,column=0,sticky='w')
        self.progress=ttk.Progressbar(page,maximum=100);self.progress.grid(row=9,column=0,sticky='ew',pady=(16,8))
        ttk.Label(page,textvariable=self.status,wraplength=650).grid(row=10,column=0,sticky='w')
        footer=ttk.Frame(page);footer.grid(row=11,column=0,sticky='ew',pady=(20,0))
        ttk.Label(footer,text='Generates the file; install it from the camera’s hidden menu.').pack(side='left')
        ttk.Button(footer,text='About',command=self.about).pack(side='right')
        root.protocol('WM_DELETE_WINDOW',self.close);root.after(100,self.poll)
    def select_source(self):
        value=filedialog.askopenfilename(parent=self.root,title='Select Kodak C713 updater',filetypes=[('Kodak updater / firmware','*.exe *.EXE *.fw *.FW'),('All files','*')])
        if value:self.source.set(value)
    def select_folder(self):
        value=filedialog.askdirectory(parent=self.root,title='Save ModernShare firmware',mustexist=True)
        if value:self.folder.set(value)
    def start(self):
        if self.busy:return
        if not self.source.get() or not self.folder.get():
            self.status.set('Select the updater and an output folder first.');return
        source=Path(self.source.get());folder=Path(self.folder.get())
        if not folder.is_dir():self.status.set('Choose an existing output folder.');return
        self.busy=True;self.progress['value']=0;self.status.set('Starting…')
        for widget in [self.button,self.browse,self.choose]:widget.configure(state='disabled')
        def worker():
            try:
                result=generate(source,folder/'KC713.FW',lambda n,s:self.events.put(('progress',(n,s))))
                self.events.put(('done',result))
            except Exception as e:self.events.put(('error',str(e)))
        threading.Thread(target=worker,daemon=True).start()
    def poll(self):
        try:
            while True:
                kind,value=self.events.get_nowait()
                if kind=='progress':self.progress['value']=value[0];self.status.set(value[1]);continue
                self.busy=False
                for widget in [self.button,self.browse,self.choose]:widget.configure(state='normal')
                if kind=='done':
                    self.status.set('Ready: '+value['path'])
                    messagebox.showinfo('ModernShare firmware ready','KC713.FW was generated and verified.\n\nCopy it to SYSTEM on the SD card, then use the camera’s UPDATE FIRMWARE action.',parent=self.root)
                else:
                    self.status.set(value);messagebox.showerror('Could not generate firmware',value,parent=self.root)
        except queue.Empty:pass
        self.root.after(100,self.poll)
    def about(self):
        messagebox.showinfo('About ModernShare','ModernShare 0.8\nAGPL-3.0-or-later\n\nSource code is distributed alongside the app release.\nIndependent project; not affiliated with Kodak.\n\nThe original Kodak updater is not included.',parent=self.root)
    def close(self):
        if self.busy:self.status.set('Finishing the firmware file. Please wait a moment.');return
        self.root.destroy()

def main():
    import sys
    if '--version' in sys.argv:
        print('ModernShare 0.8');return
    if '--smoke-test' in sys.argv:
        root=tk.Tk();App(root);root.update();root.destroy();return
    if '--headless' in sys.argv:
        import argparse,json
        p=argparse.ArgumentParser();p.add_argument('--headless',action='store_true');p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
        a=p.parse_args()
        try:print(json.dumps(generate(a.input,a.output),indent=2))
        except (ValueError,OSError) as e:p.exit(1,f'{e}\n')
        return
    root=tk.Tk();App(root);root.mainloop()

if __name__=='__main__':main()

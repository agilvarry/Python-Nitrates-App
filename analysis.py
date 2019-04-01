#import modules & check out extensions
import os
import threading
import arcpy
from arcpy import env
from arcpy.sa import *
from tkinter import *
import tkinter as tk
from tkinter import ttk
from tkinter.ttk import *
from tkinter import messagebox
from PIL import ImageTk, Image

#constants
HEIGHT = 800
WIDTH = 750
FONT = ("Veramda, 14")

#set up GUI
root = tk.Tk()
root.title('Wisconsin Nitrate Well Analysis')
root.resizable(False, False)

#function to clear content from map document
def clearMap(mapView):
    for lyr in mapView.listLayers():
        mapView.removeLayer(lyr)

#Run the analysis!
def analysis(k, status_cb, done_cb):
    layers = [] #keep track of layers to garbage collect 
    BASE_DIR = "C:\\project1files\\project1files\\"
   
    arcpy.CheckOutExtension("spatial")

    #workspace setup
    env.workspace = BASE_DIR + "workspace"
    arcpy.env.overwriteOutput = True
    arcpy.env.qualifiedFieldNames = False
    
    aprx = arcpy.mp.ArcGISProject(BASE_DIR + "777ProjectOne.aprx")
    mapView=aprx.listMaps()[0]
    lyt = aprx.listLayouts("Layout")[0]
    #- idw
    #http://pro.arcgis.com/en/pro-app/tool-reference/spatial-analyst/idw.htm
    status_cb('Running IDW from Well Nitrate data')
    inPointFeatures = BASE_DIR +"well_nitrate.shp"
    zField = "nitr_ran"
     

    outIDW = Idw(inPointFeatures, zField, power = k)
    outIDW.save("idw.tif")
    layers.append("idw.tif")
    mapView.addDataFromPath(BASE_DIR + "workspace\\idw.tif")

    referenceLayer = mapView.listLayers()[0]
    moveLayer = mapView.listLayers()[1]

    mapView.moveLayer(referenceLayer, moveLayer, "BEFORE")
    
    lyt.exportToPNG(BASE_DIR + "workspace\\IDW.png")
    
    clearMap(mapView)

    #- nitrate concentration for tracts
    #http://pro.arcgis.com/en/pro-app/tool-reference/spatial-analyst/zonal-statistics-as-table.htm
    status_cb('Running Zonal Stats')

    inZoneData = BASE_DIR + "cancer_tracts.shp"
    zoneField = "GEOID10"
    inValueRaster = "idw.tif"
    outTable = "zonal_out.dbf"
    layers.append(outTable)

    ZonalStatisticsAsTable(inZoneData, zoneField, inValueRaster, outTable, "NODATA", "MEAN")

    #- join the zoneal stats table to the cancer tracts
    #http://pro.arcgis.com/en/pro-app/tool-reference/data-management/make-feature-layer.htm

    status['text'] ='Joining Zonal Stats to Cancer Tracts'

    # Set local variables
    inFeatures = BASE_DIR + "cancer_tracts.shp"
    layerName = "cancer_tracts"
    joinTable = "zonal_out.dbf"
    joinField = "GEOID10"

    outFeature = "join_tracts"
    layers.append(outFeature)
    isCommon = "KEEP_COMMON"

    # Create a feature layer
    arcpy.MakeFeatureLayer_management (inFeatures, layerName)

    # Join the feature layer to a table
    arcpy.AddJoin_management(layerName, joinField, joinTable, joinField, isCommon)

    # Copy the layer to a new permanent feature class
    arcpy.CopyFeatures_management(layerName, outFeature)

    #- Perform regression analysis
    #add reports
    #http://pro.arcgis.com/en/pro-app/tool-reference/spatial-statistics/ordinary-least-squares.htm
    status_cb("Running Regresion")
    
    gwrIn = "join_tracts.shp"
    gwrID = "OID_"
    gwrOut = "gwrOUT"
    dependent = "canrate"
    explanVar = "MEAN"
    swm = "8Neighs"
    layers.append(gwrOut)    
    arcpy.GeographicallyWeightedRegression_stats(gwrIn, dependent, explanVar, gwrOut, "ADAPTIVE", "CV")
    
    
    status_cb("Generating Spatial Autocorrelation Report")                    
    # Calculate Moran's Index of Spatial Autocorrelation 
    # Process: Spatial Autocorrelation (Morans I)...      
    moransI = arcpy.SpatialAutocorrelation_stats("gwrOUT.shp", "Residual","GENERATE_REPORT", "INVERSE_DISTANCE", "EUCLIDEAN_DISTANCE", "NONE", "#")
    print(arcpy.GetMessages())
        
    mapView.addDataFromPath(BASE_DIR + "workspace\\gwrOut.shp")
    lyt.exportToPNG(BASE_DIR + "workspace\\GWR.png")
    
    
    for l in layers:
        arcpy.Delete_management(l) #delete created layers to remove lock files
    
    status_cb("Done! Toggle images below or re-run regression.")
    showGWR() #show output when we're done
    done_cb()

#turn button off while analysis is running
def buttonToggle():
    if button0['state'] == DISABLED:
        button0['state'] = NORMAL
    else:
        button0['state'] = DISABLED


#Thread that runs the analysis
class processThread (threading.Thread):
    def __init__(self, k, status_cb, done):
        threading.Thread.__init__(self)
        self.k = k
        self.status_cb = status_cb
        self.done = done
    def run(self):
        buttonToggle()
        status['text'] = 'Starting analysis...'
        print("Starting with K value: " + self.k)
        analysis(self.k, self.status_cb, self.done)

#########################
#  Gui Functions        #
#########################
    
def runClick():
    k = entry.get()
    if not k.isnumeric() :
        status['text'] ="Please Enter a Number to Run the Analysis"
    elif float(k) >= 1 and float(k) <= 10:
        #Init thread
        thread1 = processThread(k, status_update, buttonToggle)
        #Call the thread's "run" function
        thread1.start()
    else:     
        status['text'] = "Please Enter a Number Between 1 and 10"
def regression():
    messagebox.showinfo("Geographically Weighted Regresion","Regression is used to evaluate relationships between two or more feature attributes. Identifying and measuring relationships allows you to better understand what's going on in a place, predict where something is likely to occur, or examine causes of why things occur where they do. Geographically Weighted Rregression evaluates a local model of the variable or process you are trying to understand or predict by fitting a regression equation to every feature in the dataset. GWR constructs these separate equations by incorporating the dependent and explanatory variables of the features falling within the neighborhood of each target feature.")
def idwHelp():
    messagebox.showinfo("Inverse Weighted Distance", "Inverse Weighted Distance (IDW) is the most widely used interpolation. IDW uses the theory of close things are more related than distant things most explicitly. IDW assigns weights quantitatively based on distance from a known point. The power you enter will determine how quickly locations are no longer considered close. Typically the power value should be between 1.5 and 2.5")

def about():
    messagebox.showinfo("About", "This application searches for a relationship between nitrate levels in drinking water and cancer occurrences for census tracts in the state of Wisconsin. IDW, Regression and statistics present a possible role of water nitrate levels in cancer occurence.")
    
def showIDW():
    try:
        image = Image.open("workspace\\IDW.png")
        image = image.resize((600, 600), Image.ANTIALIAS)
        imageP = ImageTk.PhotoImage(image)
        widgetf.configure(image=imageP)
        widgetf.image = imageP
    except:
        status['text'] = "Please Run Analysis"

def showGWR():
    try:
        image = Image.open("workspace\\GWR.png")
        image = image.resize((600, 600), Image.ANTIALIAS)
        imageP = ImageTk.PhotoImage(image)
        widgetf.configure(image=imageP)
        widgetf.image = imageP
    except:
        status['text'] = "Please Run Analysis"
              
def showWell():
    try:
        image = Image.open("main.png")
        image = image.resize((600, 600), Image.ANTIALIAS)
        imageP = ImageTk.PhotoImage(image)
        widgetf.configure(image=imageP)
        widgetf.image = imageP
    except:
        status['text'] = "Oh No Something went wrong"

def status_update(text):
    status['text'] = text

def cleanup():
    root_dir = "C:\\project1files\\project1files\\workspace"
    status['text'] = 'Cleaning up...'
    for file in os.listdir(root_dir):
        try:
            os.remove(os.path.join(root_dir, file))
        except:
            print('Could not delete '+file)
    root.destroy()

#set up canvas and add to root
canvas = tk.Canvas(root, height=HEIGHT, width=WIDTH)
canvas.pack()

# creating a menu instance
menu = Menu(root)
root.config(menu=menu)
#clear out created files on window close
root.protocol("WM_DELETE_WINDOW", cleanup)

# create the file object)
info = Menu(menu)

#added "file" to our menu
menu.add_cascade(label="Info", menu=info)

# adds a command to the menu option, calling it exit, and the
# command it runs on event is client_exit
info.add_command(label="IDW", command=idwHelp)
info.add_command(label="Regression", command=regression)
info.add_command(label="About", command=about)


#set up top from for variable entry and button to run analysis
frame1 = tk.Frame(root)
frame1.place(relx=0.5, rely=0.02, relwidth=0.8, relheight=0.06, anchor='n')
entry = ttk.Entry(frame1, font=12)
entry.place(relx=0.2, relwidth=0.3, relheight=1)

button0 = tk.Button(frame1, text="Run",relief=FLAT, background="#D3D3D3", command=runClick)
button0.place(relx=0.52, relwidth=0.3, relheight=1)

#set up text label for updates and error messages
frame= tk.Frame(root, bd=1, bg="black")
frame.place(relx=0.2, rely=0.1, relheight=0.05, relwidth=0.6)
status = ttk.Label(frame, text="Please Enter a K Value and Run the Analysis", borderwidth=1, anchor=W, justify=LEFT, background="white", foreground="black", font=12)
status.place(relheight=1, relwidth=1)

#set up middle frame to displace images, add initial image
mid_frame = tk.Frame(root, bd=5, bg="black")
mid_frame.place(relx=0.5, rely=0.16, relwidth=0.8, relheight=0.75, anchor='n')
image = Image.open("main.png")
image = image.resize((600, 600), Image.ANTIALIAS)
imagePath = ImageTk.PhotoImage(image)
widgetf = tk.Label(mid_frame, image=imagePath)
widgetf.place(relwidth=1, relheight=1) 

#set up bottom frame for buttons to swap images
bottom_frame = tk.Frame(root, bd=5)
bottom_frame.place(relx=.5, rely=0.92, relwidth=0.8, relheight=0.06, anchor='n')
button1 = tk.Button(bottom_frame, text="GWR", relief=FLAT, background="#D3D3D3",  command=showGWR)
button1.place(relx=0, relwidth=0.3, relheight=1)
button2 = tk.Button(bottom_frame, text="Wells", relief=FLAT, background="#D3D3D3", command=showWell)
button2.place(relx=0.35, relwidth=0.3, relheight=1)
button3 = tk.Button(bottom_frame, text="IDW", relief=FLAT, background="#D3D3D3", command=showIDW)
button3.place(relx=0.7, relwidth=0.3, relheight=1)

root.mainloop()

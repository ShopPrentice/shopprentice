#Author-Xiaodong Liang, Autodesk
#Design Text on Surface as Extrude Feature

import adsk.core, adsk.fusion, traceback,os
import sys
fontToolPath = os.path.dirname(os.path.realpath(__file__))
fontToolPath = fontToolPath + "\\FontTools"
print(fontToolPath)
if not fontToolPath in sys.path:
    sys.path.append(fontToolPath)    
from fontTools import ttLib
 

#global definition

#command ID
commandIdOnPanel = 'id_TextOnSurface'
#enviornment to use the command
workspaceToUse = 'FusionSolidEnvironment'
#panel to put the button
panelToUse = 'SolidCreatePanel'

# global set of event handlers to keep them referenced for the duration of the command
#for command
handlers = []

#for command dialog
handlers_dialog = []

# the message to show warning
warning_text_input = None

#selected face
#because of a limitation of Fusion API in this release, 
#the command dialog does not provide the selection input. 
#The user needs to select a surface in advance, next run the command
g_currentSel = None

#fonts map
g_fontDic = None

#in case the sketches folder is switched off, switch it on
g_isSketches_On = False
 

#some default params for sketch text
defaultFontHeight = 1.0
defaultLetterGap = 0.1
defaultExtrudeDis = 1.0
defaultStartAngle = 0.1
defaultAxisDis = 0

#get edge evaluator from a surface
#Reserved
def get2DEval(cyFace):
     eval2d = None
     for loop in cyFace.loops:
        for coedge in loop.coEdges:
            eval2d = coedge.evaluator
            break
     return eval2d

######### begin functions for Font ##################
FONT_SPECIFIER_NAME_ID = 4
FONT_SPECIFIER_FAMILY_ID = 1

#short name of a truetype font
#platformID: Windows or Mac
def shortName(font,platformID):
     name = ""
     family = ""
     for record in font['name'].names:        
         if record.nameID == FONT_SPECIFIER_NAME_ID and not name and record.platformID==platformID:             
             name = record.toUnicode()
         elif record.nameID == FONT_SPECIFIER_FAMILY_ID and not family and record.platformID==platformID: 
             family = record.toUnicode()
         if name and family:
            break 
             
     return name, family
     
# get font list (Windows only in this release) 
def getFontList(dic):
    
     app = adsk.core.Application.get()
     ui = app.userInterface
     if sys.platform.startswith('win') or sys.platform.startswith('cygwin'): 
            #Windows 
            FontPath = os.path.join(os.environ['WINDIR'], 'Fonts')
            PlatFormID = 3
     elif sys.platform.startswith('darwin'): 
            #Mac machine (to test)
            #FontPath = os.environ['System']
            #PlatFormID = 1
            print('Mac')
     else:     
         if ui:
              ui.messageBox('This is an unknown OS!!')
              return       
    
     #iterate each *.ttf font in the specific folder
     for file in os.listdir(FontPath):           
        if file.lower().endswith(".ttf") or file.lower().endswith(".ttc"):                
            source_file_name = FontPath+"\\"+file
            tt = ttLib.TTFont(source_file_name,fontNumber=0) 
            font_ori_name =  shortName(tt,PlatFormID)[1]
            #store this font to fonts map
            if not font_ori_name in dic:
                dic[font_ori_name] = source_file_name

####### end of functions for Font######################

# build the features with the command inputs (Execution or Preview)
def runCommandInput(args,isPreview):
    
    global warning_text_input 
    
    app = adsk.core.Application.get()
    ui = app.userInterface
    unitsMgr = app.activeProduct.unitsManager
            
    #unit enum
    d = {0:'mm',
          1:'cm',
          2:'m',
          3:'inch',
          4:'foot'}  
    #unit of this design      
    currentLenUnit = unitsMgr.formatUnits( d[unitsMgr.distanceDisplayUnits] )           
    
    try:
        command = args.firingEvent.sender
        #command inputs
        inputs = command.commandInputs  
        
        #emboss text instance to store the params             
        embossText = EmbossTextClass()
        for input in inputs:
            if input.id == 'textString':
                    embossText.textString = input.value
                    
            #because of a limitation of Fusion API in this release, 
            #the command dialog does not provide the selection input. 
            #The user needs to select a surface in advance, next run the command
            #reserve this input for future
                
            #elif input.id == 'cylinderFace':
            #    embossText.cylinderFace = input.selection(0).entity                     
                    
            elif input.id == 'fontHeight':
                embossText.fontHeight = unitsMgr.evaluateExpression(input.expression, currentLenUnit)
            elif input.id == 'letterGap':
                embossText.letterGap = unitsMgr.evaluateExpression(input.expressionOne, "rad")
            elif input.id == 'booleanMethod':
                embossText.booleanMethod = input.selectedItem.name
            elif input.id == 'extrudeDis':
                embossText.extrudeDis = unitsMgr.evaluateExpression(input.expression, currentLenUnit)
            elif input.id == 'startAngle':
                embossText.startAngle = unitsMgr.evaluateExpression(input.expressionOne, "rad")
            elif input.id == 'isBold':
                embossText.isBold = input.value
            elif input.id == 'isItalic':
                embossText.isItalic = input.value
            elif input.id == 'isUnderlined':
                embossText.isUnderlined = input.value
            elif input.id == 'textAngle':
                embossText.textAngle = unitsMgr.evaluateExpression(input.expressionOne, "rad")
            elif input.id == 'isFlipEmboss':
                embossText.isFlipEmboss = input.value
            elif input.id == 'axisDis':
                embossText.axisDis = unitsMgr.evaluateExpression(input.expression, currentLenUnit)
            elif input.id == 'fontName':
               embossText.fontName = input.selectedItem.name                                  
            if input.id == 'isUpsideDown':
                embossText.isUpsideDown = input.value
            if input.id == 'isBackwards':
                embossText.isBackwards = input.value                    
            if input.id == 'isVertical':
                embossText.isVertical = input.value
            
        #try to create the result text feature
        embossText.buildTextSketches()     
        if isPreview:                
            isApply = command.commandInputs.itemById('isApply').value            
            if isApply == True:
                embossText.buildTextFeatures() 
        else:
            embossText.buildTextFeatures()
           
        args.isValidResult = True
        warning_text_input.value = ''
    except:          
        if warning_text_input:
             warning_text_input.value = "Bad Input! This might be due to invalid font name or no material for Cut feature"    
    

# execution of command dialog ([OK] button)
class EmbossTextCommandExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args): 
        runCommandInput(args,False) 

# preview inputs of command dialog 
class EmbossTextPreviewCommandExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args): 
        runCommandInput(args,True)
                
# when command dialog is destroyed
class EmbossTextCommandDestroyHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        app = adsk.core.Application.get()
        ui = app.userInterface
        
        product = app.activeProduct
        #current component
        rootComp = product.rootComponent 
        
        #reset the status of sketches folder
        global g_isSketches_On
        rootComp.isSketchFolderLightBulbOn =  g_isSketches_On  
        
        try:
            # when the command is done, terminate the script
            # this will release all globals which will remove all event handlers
            global g_currentSel
            g_currentSel = None

            #clearn up the handlers of command dialog.
            #next time when the dialog is invoked, all inputs will be created again
            global handlers_dialog
            handlers_dialog = []

            #since the command itself is also running within the callback. DO NOT
            #terminate it
            #adsk.terminate()
 

        except:
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


# Handle the input changed event.
#Reserved
class EmbossTextInputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        app = adsk.core.Application.get()
        ui  = app.userInterface
        try:
            command = args.firingEvent.sender           
        except:
            if ui:
                ui.messageBox('Input change failed')
                
#Initialize the events and inputs
class EmbossTextCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        app = adsk.core.Application.get()
        ui = app.userInterface 
          

        global g_currentSel
        if g_currentSel == None:
            if ui.activeSelections.count > 0:
                g_currentSel = ui.activeSelections.item(0).entity                
            else:
                ui.messageBox('Please select a cylindrical face in advance!')
                return
                
                
        product = app.activeProduct
        #current component
        rootComp = product.rootComponent          
        global g_isSketches_On
        g_isSketches_On = rootComp.isSketchFolderLightBulbOn
        rootComp.isSketchFolderLightBulbOn = True 

        try:
            cmd = args.command
            #execution  of the command dialog
            onExecute = EmbossTextCommandExecuteHandler()
            cmd.execute.add(onExecute)
            #preview of the command dialog; use the same workflow of execution
            onExecutePreview = EmbossTextPreviewCommandExecuteHandler()
            cmd.executePreview.add(onExecutePreview)
            #destroy of the command dialog
            onDestroy = EmbossTextCommandDestroyHandler()
            cmd.destroy.add(onDestroy)
            
            onInputChanged =  EmbossTextInputChangedHandler()
            cmd.inputChanged.add(onInputChanged)

            # keep the handler referenced beyond this function
            handlers_dialog.append(onExecute)
            handlers_dialog.append(onExecutePreview)
            handlers_dialog.append(onDestroy)

            #current unit
            unitsMgr = app.activeProduct.unitsManager
            d = {0:'mm',
                  1:'cm',
                  2:'m',
                  3:'inch',
                  4:'foot'}     
            currentLenUnit = unitsMgr.formatUnits( d[unitsMgr.distanceDisplayUnits] )
           
            
            #define the inputs
            inputs = cmd.commandInputs

           

            #text string
            inputs.addStringValueInput('textString', 'Text', '')

            #note: because of the limitation of Fusion API, the command dialog does not provide the
            #selection input. The user needs to select a surface in advance, next run the command
            #Reserved these lines for future
    
            #selInput = inputs.addSelectionInput('cylinderFace',
            #'Select a Cylinder Face',
            #'Select a Cylinder Face')
            #selInput.setSelectionLimits(1,1)
            #selInput.addSelectionFilter('CylindricalFaces')

            #font list
            #trying to find way to get OS fonts list automatically
            font_dropdown = inputs.addDropDownCommandInput('fontName','Font Name',adsk.core.DropDownStyles.TextListDropDownStyle)
            global g_fontDic
            g_fontDic = {}
            getFontList(g_fontDic)
            newDic = sorted(g_fontDic.keys())
            selectedKey = None
            for key in newDic:
                currentKey = font_dropdown.listItems.add(key,True,'./resources',-1)
                if key == 'Arial':
                    selectedKey = currentKey
            #font_dropdown.selectedItem = selectedKey           

            #font height
            initFontHeight = adsk.core.ValueInput.createByReal(defaultFontHeight)
            inputs.addValueInput('fontHeight', 'Font Height',currentLenUnit,initFontHeight)

            #font is bold
            inputs.addBoolValueInput('isBold','Bold',True,'./resources',False)
            #font is italic
            inputs.addBoolValueInput('isItalic','Italic',True,'./resources',False)
            #font is underlined - no use. in UI, underline is also ignored if extruding a text
            #inputs.addBoolValueInput('isUnderlined','Underlined',True,'./resources',False)
            #text angle in the sketch plane
            inputs.addFloatSliderCommandInput('textAngle','Text Angle', 'rad', 0, 6.28,False)
            #text start angle along the parameters range
            startAngleV = inputs.addFloatSliderCommandInput('startAngle','Start Angle', 'rad', 0, 6.28,False)
            #set a default start angle
            startAngleV.expressionOne = '0.0 rad'

            #is text upside down
            isUpsideDown = inputs.addBoolValueInput('isUpsideDown','Upside Down',True,'./resources',False)
            isUpsideDown.value = False
           

            #the distance of text position along axis direction
            initAxisDis = adsk.core.ValueInput.createByReal(defaultAxisDis)
            inputs.addValueInput('axisDis', 'Distance at Axis', currentLenUnit, initAxisDis)

            #distance of each letter
            lettgap = inputs.addFloatSliderCommandInput('letterGap','Letter Gap', 'rad', 0, 3.14,False)
            lettgap.expressionOne = '0.0 rad'
            
             #is text backwards
            isBackwards = inputs.addBoolValueInput('isBackwards','Reverse',True,'./resources',False)
            isBackwards.value = False
            
            #is text backwards
            #isVertical = inputs.addBoolValueInput('isVertical','Vertical',True,'./resources',False)
            #isVertical.value = False

            #method to create the text feature: Cut or Join
            booleanMethod_dropdown = inputs.addDropDownCommandInput('booleanMethod','Boolean Method',1)
            booleanMethod_dropdown.listItems.add('Cut',True,'./resources',-1)
            booleanMethod_dropdown.listItems.add('Join',False,'./resources',-1)

            #if flip the text feature: e.g. in Cut mode, feature creation might fail because
            #no material the text feature can cut. so flip the feature to the other side that
            #has material.
            isFlipEmboss = inputs.addBoolValueInput('isFlipEmboss','Flip Emboss',True,'./resources',False)
            isFlipEmboss.value = True
            #emboss distance of text feature
            initExtrudeDis = adsk.core.ValueInput.createByReal(defaultExtrudeDis)
            inputs.addValueInput('extrudeDis', 'Emboss Distance', currentLenUnit, initExtrudeDis)           
            

            global warning_text_input
            warning_text_input = inputs.addStringValueInput('warningText', 'Warning', '')
            warning_text_input.isEnabled = True
            
            isApply = inputs.addBoolValueInput('isApply','Apply',True,'./resources',False)
            isApply.value = False
 
        except:
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

#Text feature params and creation class
class EmbossTextClass:
    def __init__(self):
        #text string
        self._textString = ''
        #selected face: no use now, reserved
        self._cylinderFace  = None
        #font height
        self._fontHeight = adsk.core.ValueInput.createByReal(defaultFontHeight)
        #distance of each letter
        self._letterGap = adsk.core.ValueInput.createByReal(defaultLetterGap)
        #method to create the text feature
        self._booleanMethod = 1  #1. cut, 0, join
        #emboss distance
        self._extrudeDis = adsk.core.ValueInput.createByReal(defaultExtrudeDis)
        #text start angle along the parameters range
        self._startAngle = adsk.core.ValueInput.createByReal(defaultStartAngle)
        #font name
        self._fontName = 'Arial'
        #is font bold
        self._isBold = False
        #is font italic
        self._isItalic = False
        #is font underlined
        self._isUnderlined = False
        #text angle in the sketch plane
        self._textAngle = 0
        #the distance of text position along axis direction
        self._axisDis = 0
        #if flip the text feature: e.g. in Cut mode, feature creation might fail because
        #no material the text feature can cut. so flip the feature to the other side that
        #has material.
        self._isFlipEmboss = False
        #workaround for font name
        self._fontName_by_typing = 'Arial'
        #is upside down
        self._isUpsideDown = False
        #is backwards
        self._isVertical = False
        #sketch collection
        #self._sketchCollection = adsk.core.ObjectCollection.create()
        self._tl_group_index = -1
      

    #properties
    @property
    def textString(self):
        return self._textString
    @textString.setter
    def textString(self, value):
        self._textString = value

    @property
    def cylinderFace(self):
        return self._cylinderFace
    @cylinderFace.setter
    def cylinderFace(self, value):
        self._cylinderFace = value

    @property
    def fontName(self):
        return self._fontName
    @fontName.setter
    def fontName(self, value):
        self._fontName = value

    @property
    def fontHeight(self):
        return self._fontHeight
    @fontHeight.setter
    def fontHeight(self, value):
        self._fontHeight = value

    @property
    def isBold(self):
        return self._isBold
    @isBold.setter
    def isBold(self, value):
        self._isBold = value

    @property
    def isItalic(self):
        return self._isItalic
    @isItalic.setter
    def isItalic(self, value):
        self._isItalic = value

    @property
    def isUnderlined(self):
        return self._isUnderlined
    @isUnderlined.setter
    def isUnderlined(self, value):
        self._isUnderlined = value

    @property
    def textAngle(self):
        return self._textAngle
    @textAngle.setter
    def textAngle(self, value):
        self._textAngle = value


    @property
    def isUpsideDown(self):
        return self._isUpsideDown
    @isUpsideDown.setter
    def isUpsideDown(self, value):
        self._isUpsideDown = value

    @property
    def isBackwards(self):
        return self._isBackwards
    @isBackwards.setter
    def isBackwards(self, value):
        self._isBackwards = value
        
    @property
    def isVertical(self):
        return self._isVertical
    @isVertical.setter
    def isVertical(self, value):
        self._isVertical = value

    @property
    def axisDis(self):
        return self._axisDis
    @axisDis.setter
    def axisDis(self, value):
        self._axisDis = value

    @property
    def letterGap(self):
        return self._booleanMethod
    @letterGap.setter
    def letterGap(self, value):
        self._booleanMethod = value

    @property
    def booleanMethod(self):
        return self._headHeight
    @booleanMethod.setter
    def booleanMethod(self, value):
        self._headHeight = value

    @property
    def isFlipEmboss(self):
        return self._isFlipEmboss
    @isFlipEmboss.setter
    def isFlipEmboss(self, value):
        self._isFlipEmboss = value

    @property
    def extrudeDis(self):
        return self._extrudeDis
    @extrudeDis.setter
    def extrudeDis(self, value):
        self._extrudeDis = value

    @property
    def startAngle(self):
        return self._startAngle
    @startAngle.setter
    def startAngle(self, value):
        self._startAngle = value

    @property
    def fontName_by_typing(self):
        return self._fontName_by_typing
    @fontName_by_typing.setter
    def fontName_by_typing(self, value):
        self._fontName_by_typing = value
     
     
    @property
    def tl_group_index(self):
        return self._tl_group_index
    @tl_group_index.setter
    def tl_group_index(self, value):
        self._tl_group_index = value 


    #try to create the result text feature
    def buildTextSketches(self):

        app = adsk.core.Application.get()
        ui = app.userInterface
        
        #design
        product = app.activeProduct
        #timeliner
        fusiontimeliner = product.timeline
        #current component
        rootComp = product.rootComponent         
        
        
        global g_currentSel
        if g_currentSel!= None:                 
            try:
                global g_fontDic
                tt = None
                #if the font exists in the font list
                if self.fontName in g_fontDic:
                    #path of the font file
                    FontPath = g_fontDic[self.fontName]                  
                    #truetype font 
                    tt = ttLib.TTFont(FontPath,fontNumber=0)   
                else:
                    if warning_text_input:
                        warning_text_input.value = "Invalid Font!"
                    return                    
                    
                #evaluator of the surface
                eval3d = g_currentSel.geometry.evaluator
                radius = g_currentSel.geometry.radius
                
                #default start angle in parameters range for the first letter
                thisP = self.startAngle
                realP = thisP
                
                #char index in the string
                index = 0   
                #X position of the char along string direction
                baseX = 0
                #last char
                lastChar = ""                 
                
                #index for timeliner group of sketches
                tl_group_stIndex = 0
                tl_group_endIndex = 0
                
                #iterate each letter
                for eachChar in self.textString: 
                    
                    if eachChar == ' ':
                        #if it is a space, step is set to 0.5 of font size
                        baseX = self.fontHeight /2.0                
                        
                        #param 
                        if self.isBackwards:
                            #if backward, text direction is reversed
                            thisP = thisP - baseX / radius  - self.letterGap
                        else:   
                            thisP = thisP + baseX / radius  + self.letterGap 
                        continue
                    else:  
                     
                        (baseX,baseY,xMax,xMin) = getGlyf(tt,lastChar,eachChar,self.fontHeight)                         
                        if self.isBackwards:
                            thisP = thisP - baseX / radius - self.letterGap
                            realP = thisP - 0.5 * (xMax + xMin) / radius
                        else:
                            thisP = thisP + baseX / radius + self.letterGap
                            realP = thisP + 0.5 * (xMax + xMin) / radius
 
                     
                    #get 3D position of this param    
                    pt_2d_1 = adsk.core.Point2D.create(0,thisP)
                    (ReturnValue, pt_3d_1) = eval3d.getPointAtParameter(pt_2d_1)
                    cons_input =  rootComp.constructionPoints.createInput()
                    cons_input.setByPoint(pt_3d_1)
                    x_1 = pt_3d_1.x
                    y_1 = pt_3d_1.y
                    z_1 = pt_3d_1.z
                    #rootComp.constructionPoints.add(cons_input)

                    
                    pt_2d = adsk.core.Point2D.create(0,realP)
                    (ReturnValue, pt_3d) = eval3d.getPointAtParameter(pt_2d)
                    cons_input =  rootComp.constructionPoints.createInput()
                    cons_input.setByPoint(pt_3d)
                    #rootComp.constructionPoints.add(cons_input)
                    x = pt_3d.x
                    y = pt_3d.y
                    z = pt_3d.z   
                    rootComp.constructionPoints.add(cons_input)
                    
                    pts = []
                    pts.append(pt_3d)
                    #normal at this 3D position
                    (ReturnValue, normals) = eval3d.getNormalsAtPoints(pts)
                    #U V (X, Y) direction at this 3D position
                    (ReturnValue, partialU, partialV) = eval3d.getFirstDerivative(pt_2d)
                    #create a plane on the 3D position and U V.
                    plane = adsk.core.Plane.create(pt_3d_1,normals[0])
                    
                    if self.isUpsideDown:
                        partialU.x = -partialU.x
                        partialU.y = -partialU.y
                        partialU.z = -partialU.z
                    if self.isBackwards:                             
                        partialV.x = -partialV.x         
                        partialV.y = -partialV.y
                        partialV.z = -partialV.z
   
                    plane.setUVDirections(partialV,partialU)    
                    cons_planes = rootComp.constructionPlanes
                    cons_planeInput = cons_planes.createInput()
                    cons_planeInput.setByPlane(plane)
                    cons_plane = cons_planes.add(cons_planeInput)

                    #create a sketch from this plane
                    sketches = rootComp.sketches
                    sketch = sketches.add(cons_plane) 

                    #create the text of this letter on this sketch
                    sketch_texts = sketch.sketchTexts 
                   
                   
                    txt_pos = adsk.core.Point3D.create(pt_3d_1.x + partialU.x * self.axisDis,
                                                       pt_3d_1.y + partialU.y * self.axisDis,
                                                       pt_3d_1.z + partialU.z * self.axisDis  )


                    txt_pos_in_sketch = sketch.modelToSketchSpace(txt_pos)
                    txt_pos_in_sketch.y = txt_pos_in_sketch.y + baseY
                    
                    sketch_text_input = sketch_texts.createInput(eachChar,
                                                                 self.fontHeight,
                                                                 txt_pos_in_sketch)
                    #parameters of this text

                    sketch_text_input.fontName = self.fontName
                    #sketch_text_input.fontName = 'Arial'
                    this_letter_in_sketch = sketch_texts.add(sketch_text_input)
                    this_letter_in_sketch.angle = self.textAngle

                    txtStyle = 0
                    if self.isBold:
                        txtStyle = txtStyle + 1
                    if self.isItalic:
                        txtStyle = txtStyle + 2
                    if self.isUnderlined:
                        txtStyle = txtStyle + 4

                    this_letter_in_sketch.textStyle = txtStyle
                    sketch.isVisible  = True 
                    
                    #index for timeliner group
                    if index == 0:
                        tl_group_stIndex = sketch.timelineObject.index                     
                    tl_group_endIndex = sketch.timelineObject.index  
                    
                    index = index +1                    
                    #store the last char for calculation of next char
                    lastChar = eachChar
                    
                #create a new timeliner group    
                tl_group = fusiontimeliner.timelineGroups.add(tl_group_stIndex,tl_group_endIndex)                                
                
                #store the group index for creating extrude feature
                self._tl_group_index = tl_group.index              
            except:
               print('except') 
        else:
             ui.messageBox('Please select a cylindrical face in advance!')
             
    def buildTextFeatures(self):
        app = adsk.core.Application.get()         
        product = app.activeProduct
        #current component
        rootComp = product.rootComponent
        
        
        extrudes = rootComp.features.extrudeFeatures 
        
        fusiontimeliner = product.timeline
        if self._tl_group_index > -1:
            tl_group = fusiontimeliner.item(self._tl_group_index)
            sketch_index = 0
            
            tl_group_extrudes_stIndex = 0
            tl_group_extrudes_endIndex = 0
            
            for sketch_index in range(0, tl_group.count): 
                    eachSketch = tl_group.item(sketch_index).entity
                    eachSketchT = eachSketch.sketchTexts.item(0)
                    
                    if self.booleanMethod== 'Cut':
                        extInput = extrudes.createInput(eachSketchT,
                                                    adsk.fusion.FeatureOperations.CutFeatureOperation)
                    else:
                        extInput = extrudes.createInput(eachSketchT,
                                                    adsk.fusion.FeatureOperations.JoinFeatureOperation)
            
                    if self.isFlipEmboss:
                        thisExtrudeDis = adsk.core.ValueInput.createByReal(-self.extrudeDis)
                    else:
                        thisExtrudeDis = adsk.core.ValueInput.createByReal(self.extrudeDis)
                        
                    #try to create the text feature
                    extInput.setDistanceExtent(True, thisExtrudeDis)
                    thisExtrudeF = extrudes.add(extInput) 
                    
                    #index for timeliner group
                    if sketch_index == 0:
                        tl_group_extrudes_stIndex = thisExtrudeF.timelineObject.index
                    tl_group_extrudes_endIndex = thisExtrudeF.timelineObject.index    
              
            #create a new timeliner group      
            tl_group = fusiontimeliner.timelineGroups.add(tl_group_extrudes_stIndex,tl_group_extrudes_endIndex)    


#calculate the glyf of each char according to the maps in truetype font     
def getGlyf(tt,lastChar,thisChar,fontsize):
      
      baseX = 0
      baseY = 0
      xMax = 0
      xMin = 0    
      
      #tt = ttLib.TTFont(FontPath,fontNumber=0)   
      unitsPerEm = tt['head'].unitsPerEm
     
      glyf = tt['glyf']
      cmap = tt['cmap']   
      hmtx = tt['hmtx']
      kern = tt['kern']
    
      MS_cmap = cmap.getcmap(3,1).cmap    
      hmtx_table = hmtx.metrics
      kern_table = kern.kernTables[0].kernTable
      
      char_Code = ord(thisChar)
      char_Name = MS_cmap[char_Code]
     
      char_Glyf  = glyf[char_Name]           
      
      char_AdvWidth = hmtx_table[char_Name][0]
      
      char_LSB= hmtx_table[char_Name][1]
     
      
      baseY= char_Glyf.yMin  * fontsize / unitsPerEm
      
      xMin = char_Glyf.xMin  * fontsize / unitsPerEm
      xMax = char_Glyf.xMax  * fontsize / unitsPerEm
     
            
      if lastChar !='' and lastChar!= ' ':  
            lastChar_Code = ord(lastChar) 
            lastChar_Name = MS_cmap[lastChar_Code]
            lastChar_Glyf  = glyf[lastChar_Name]           
           
            lastChar_AdvWidth = hmtx_table[lastChar_Name][0]
          
            lastChar_LSB= hmtx_table[lastChar_Name][1]
          
            
            if (lastChar_Name,char_Name) in kern_table:                    
                char_Pair = kern_table[(lastChar_Name,char_Name)]  
            else:
                char_Pair = 0
            
            baseX = (lastChar_AdvWidth + char_Pair) * fontsize / unitsPerEm  
            
      return baseX,baseY,xMax,xMin
          

######### scope of add-in definition ###############
def commandDefinitionById(id):
    app = adsk.core.Application.get()
    ui = app.userInterface
    if not id:
        ui.messageBox('commandDefinition id is not specified')
        return None
    commandDefinitions_ = ui.commandDefinitions
    commandDefinition_ = commandDefinitions_.itemById(id)
    return commandDefinition_

def commandControlByIdForPanel(id):
    app = adsk.core.Application.get()
    ui = app.userInterface
    if not id:
        ui.messageBox('commandControl id is not specified')
        return None

    workspaces_ = ui.workspaces
    modelingWorkspace_ = workspaces_.itemById(workspaceToUse)
    toolbarPanels_ = modelingWorkspace_.toolbarPanels
    toolbarPanel_ = toolbarPanels_.itemById(panelToUse)
    toolbarControls_ = toolbarPanel_.controls
    toolbarControl_ = toolbarControls_.itemById(id)
    return toolbarControl_

def destroyObject(uiObj, tobeDeleteObj):
    if uiObj and tobeDeleteObj:
        if tobeDeleteObj.isValid:
            tobeDeleteObj.deleteMe()
        else:
            uiObj.messageBox('tobeDeleteObj is not a valid object')

def run(context):
    ui = None
    try:
        commandName = 'Surface Text'
        commandDescription = "Place text on any surface with its letters distributed along the surface's parametric space"
        commandResources = './resources/command'

        app = adsk.core.Application.get()
        ui = app.userInterface 
 
        commandDefinitions_ = ui.commandDefinitions

        # add a command on create panel in modelling workspace
        workspaces_ = ui.workspaces
        modelingWorkspace_ = workspaces_.itemById(workspaceToUse)
        toolbarPanels_ = modelingWorkspace_.toolbarPanels
        toolbarPanel_ = toolbarPanels_.itemById(panelToUse)
        toolbarControlsPanel_ = toolbarPanel_.controls
        toolbarControlPanel_ = toolbarControlsPanel_.itemById(commandIdOnPanel)
        if not toolbarControlPanel_:
            commandDefinitionPanel_ = commandDefinitions_.itemById(commandIdOnPanel)
            if not commandDefinitionPanel_:
                commandDefinitionPanel_ = commandDefinitions_.addButtonDefinition(commandIdOnPanel, commandName, commandName, commandResources)
                commandDefinitionPanel_.tooltipDescription = commandDescription

            onCommandCreated = EmbossTextCommandCreatedHandler() # CommandCreatedEventHandlerPanel()
            commandDefinitionPanel_.commandCreated.add(onCommandCreated)
            # keep the handler referenced beyond this function
            handlers.append(onCommandCreated)
            toolbarControlPanel_ = toolbarControlsPanel_.addCommand(commandDefinitionPanel_, commandIdOnPanel)
            toolbarControlPanel_.isVisible = True

    except:
        if ui:
            ui.messageBox('AddIn Start Failed:\n{}'.format(traceback.format_exc()))

def stop(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface 

        objArrayPanel = []

        commandControlPanel_ = commandControlByIdForPanel(commandIdOnPanel)
        if commandControlPanel_:
            objArrayPanel.append(commandControlPanel_)

        commandDefinitionPanel_ = commandDefinitionById(commandIdOnPanel)
        if commandDefinitionPanel_:
            objArrayPanel.append(commandDefinitionPanel_)

        for obj in objArrayPanel:
            destroyObject(ui, obj)

        #adsk.terminate()

    except:
        if ui:
            ui.messageBox('AddIn Stop Failed:\n{}'.format(traceback.format_exc()))
######### end of add-in definition ###############
#  Copyright 2022 by Autodesk, Inc.
#  Permission to use, copy, modify, and distribute this software in object code form
#  for any purpose and without fee is hereby granted, provided that the above copyright
#  notice appears in all copies and that both that copyright notice and the limited
#  warranty and restricted rights notice below appear in all supporting documentation.
#
#  AUTODESK PROVIDES THIS PROGRAM "AS IS" AND WITH ALL FAULTS. AUTODESK SPECIFICALLY
#  DISCLAIMS ANY IMPLIED WARRANTY OF MERCHANTABILITY OR FITNESS FOR A PARTICULAR USE.
#  AUTODESK, INC. DOES NOT WARRANT THAT THE OPERATION OF THE PROGRAM WILL BE
#  UNINTERRUPTED OR ERROR FREE.
import adsk.core
import adsk.fusion
import os
from ...lib import fusion360utils as futil
from ... import config
app = adsk.core.Application.get()
ui = app.userInterface


CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_duplicate_components'
CMD_NAME = 'Duplicate Components'
CMD_Description = 'Quickly create many duplicate components'

IS_PROMOTED = False
WORKSPACE_ID = 'FusionSolidEnvironment'
PANEL_ID = 'SolidCreatePanel'
COMMAND_BESIDE_ID = 'PatternDropDown'
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', '')

local_handlers = []


# Executed when add-in is run.
def start():
    # Create a command Definition.
    cmd_def = ui.commandDefinitions.addButtonDefinition(CMD_ID, CMD_NAME, CMD_Description, ICON_FOLDER)

    # Define an event handler for the command created event. It will be called when the button is clicked.
    futil.add_handler(cmd_def.commandCreated, command_created)

    # ******** Add a button into the UI so the user can run the command. ********
    # Get the target workspace the button will be created in.
    workspace = ui.workspaces.itemById(WORKSPACE_ID)

    # Get the panel the button will be created in.
    panel = workspace.toolbarPanels.itemById(PANEL_ID)

    # Create the button command control in the UI after the specified existing command.
    control = panel.controls.addCommand(cmd_def, COMMAND_BESIDE_ID, False)

    # Specify if the command is promoted to the main toolbar. 
    control.isPromoted = IS_PROMOTED


# Executed when add-in is stopped.
def stop():
    # Get the various UI elements for this command
    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    panel = workspace.toolbarPanels.itemById(PANEL_ID)
    command_control = panel.controls.itemById(CMD_ID)
    command_definition = ui.commandDefinitions.itemById(CMD_ID)

    # Delete the button command control
    if command_control:
        command_control.deleteMe()

    # Delete the command definition
    if command_definition:
        command_definition.deleteMe()


def command_created(args: adsk.core.CommandCreatedEventArgs):
    inputs = args.command.commandInputs

    # Create a selection input.
    selectionInput = inputs.addSelectionInput('selection', 'Select', 'Select a component to duplicate')
    selectionInput.setSelectionLimits(1, 1)
    selectionInput.addSelectionFilter("Occurrences")

    # Create integer  input.
    inputs.addIntegerSpinnerCommandInput('spinnerInt', 'Number of Copies', 2, 1000, 1, 2)

    # Create boolean input
    inputs.addBoolValueInput('expandX', 'Expand components in X Direction', True, '', True)

    # Add handlers for preview and destroy
    futil.add_handler(args.command.executePreview, command_preview, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)


def command_preview(args: adsk.core.CommandEventArgs):
    # Get a reference to your command's inputs.
    inputs = args.command.commandInputs

    # Getting our inputs here
    selectionInput: adsk.core.SelectionCommandInput = inputs.itemById('selection')
    spinnerInput: adsk.core.IntegerSpinnerCommandInput = inputs.itemById('spinnerInt')
    expand_x_input: adsk.core.BoolValueCommandInput = inputs.itemById('expandX')

    selectedOccurrence: adsk.fusion.Occurrence = selectionInput.selection(0).entity
    if selectedOccurrence.objectType != adsk.fusion.Occurrence.classType():
        ui.messageBox("Can't select root component")
        selectionInput.clearSelection()
        return

    selectedComponent: adsk.fusion.Component = selectedOccurrence.component
    parent_component = selectedOccurrence.sourceComponent

    numberComponents = spinnerInput.value
    expandX: bool = expand_x_input.value

    # Used to setup x transformation
    bounding_box = selectedOccurrence.boundingBox
    max_point_x = bounding_box.maxPoint.x
    bounding_box_x = max_point_x - bounding_box.minPoint.x
    x_increment = bounding_box_x * 1.1

    for i in range(numberComponents):
        # Create a transform for the copied component
        transformMatrix = selectedOccurrence.transform

        # Increment copies of component in x direction
        if expandX:
            x_transform = ((i + 1) * x_increment) + transformMatrix.translation.x
            x_vector = adsk.core.Vector3D.create(1, 0, 0)
            x_vector.scaleBy(x_transform)
            transformMatrix.translation = x_vector

        # Create a copy of the original component
        parent_component.occurrences.addExistingComponent(selectedComponent, transformMatrix)

    args.isValidResult = True


def command_destroy(args: adsk.core.CommandEventArgs):
    global local_handlers
    local_handlers = []

#!/usr/bin/env python3

"""
Extension for InkScape 1.0

Import any DWG or DXF file using ODA File Converter, sk1 UniConvertor, ezdxf and more tools.

Author: Mario Voigt / FabLab Chemnitz
Mail: mario.voigt@stadtfabrikanten.org
Date: 23.08.2020
Last patch: 04.04.2021
License: GNU GPL v3

Module licenses
- ezdxf (https://github.com/mozman/ezdxf) - MIT License
- node.js (https://raw.githubusercontent.com/nodejs/node/master/LICENSE) - MIT License
- https://github.com/bjnortier/dxf - MIT License
- ODA File Converter - not bundled (due to restrictions by vendor)
- sk1 UniConvertor (https://github.com/sk1project/uniconvertor) - AGPL v3.0 - not bundled
- kabeja (http://kabeja.sourceforge.net/) - Apache v2
- vpype (https://github.com/abey79/vpype) - MIT License
- vpype-dxf (https://github.com/tatarize/vpype-dxf) - MIT License

ToDos:
- change copy commands to movefile commands (put into temp. sub directories where the input file is located). We need to copy files in this script because ODA File Converter will process whole dirs instead of single files only.DXF files can be really large, which slows the process)
"""

import inkex
import sys
import os
import re
import subprocess
import tempfile
from lxml import etree
from subprocess import Popen, PIPE
import shutil
from shutil import which
from pathlib import Path    
from mimetypes import MimeTypes
import urllib.request as urllib

#ezdxf related imports
import matplotlib.pyplot as plt
import ezdxf 
from ezdxf.addons.drawing import RenderContext, Frontend
#from ezdxf.addons.drawing.matplotlib_backend import MatplotlibBackend for older ezdxf library 0.14.1
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend #for recent ezdxf library 0.15.2
from ezdxf.addons import Importer

class DXFDWGImport(inkex.EffectExtension):
    def __init__(self):
        inkex.Effect.__init__(self)
        
        #blank tabs
        self.arg_parser.add_argument("--tab")
        
        #general
        self.arg_parser.add_argument("--inputfile")   
        self.arg_parser.add_argument("--dxf_to_svg_parser",                     default="bjnortier",  help="Choose a DXF to SVG parser")
        self.arg_parser.add_argument("--resizetoimport",    type=inkex.Boolean, default=True,         help="Resize the canvas to the imported drawing's bounding box") 
        self.arg_parser.add_argument("--extraborder",       type=float,         default=0.0)
        self.arg_parser.add_argument("--extraborder_units")      

        #ODA File Converter        
        self.arg_parser.add_argument("--oda_fileconverter", default=r"C:\Program Files\ODA\oda_fileconverter_title 21.6.0\oda_fileconverter.exe", help="Full path to 'oda_fileconverter.exe'")
        self.arg_parser.add_argument("--oda_hidewindow",        type=inkex.Boolean, default=True,           help="Hide ODA GUI window")
        self.arg_parser.add_argument("--oda_outputformat",                          default="ACAD2018_DXF", help="ODA AutoCAD Output version")
        self.arg_parser.add_argument("--oda_keepconverted_dxf", type=inkex.Boolean, default=True,           help="Keep ODA converted DXF file")
        self.arg_parser.add_argument("--oda_skip_dxf_to_dxf",   type=inkex.Boolean, default=False,          help="Skip conversion from DXF to DXF")
        self.arg_parser.add_argument("--oda_audit_repair",      type=inkex.Boolean, default=True,           help="Perform audit / autorepair")

        #sk1 UniConvertor
        self.arg_parser.add_argument("--sk1_uniconverter", default=r"C:\Program Files (x86)\sK1 Project\UniConvertor-1.1.6\uniconvertor.cmd", help="Full path to 'uniconvertor.cmd'")
        self.arg_parser.add_argument("--opendironerror", type=inkex.Boolean, default=True, help="Open containing output directory on conversion errors")

        #ezdxf preprocessing
        self.arg_parser.add_argument("--ezdxf_output_version",                    default="SAME", help="ezdxf output version")  
        self.arg_parser.add_argument("--ezdfx_keep_preprocessed", type=inkex.Boolean, default=True, help="Keep ezdxf preprocessed DXF file")        
        self.arg_parser.add_argument("--ezdxf_preprocessing", type=inkex.Boolean, default=True)
        self.arg_parser.add_argument("--allentities",         type=inkex.Boolean, default=True)
        
        #vpype-dxf (dread)
        self.arg_parser.add_argument("--vpype_quantization",  type=float, default=0.1, help="Maximum length of segments approximating curved elements (default 0.1mm)")
        self.arg_parser.add_argument("--vpype_simplify", type=inkex.Boolean, default=False, help="Simplify curved elements")
        self.arg_parser.add_argument("--vpype_parallel", type=inkex.Boolean, default=False, help="Multiprocessing curve conversion")  
        
        #sk1 compatible entities
        self.arg_parser.add_argument("--THREE_DFACE",   type=inkex.Boolean, default=True) #3DFACE
        self.arg_parser.add_argument("--ARC",           type=inkex.Boolean, default=True)
        self.arg_parser.add_argument("--BLOCK",         type=inkex.Boolean, default=True)
        self.arg_parser.add_argument("--CIRCLE",        type=inkex.Boolean, default=True)
        self.arg_parser.add_argument("--ELLIPSE",       type=inkex.Boolean, default=True)
        self.arg_parser.add_argument("--LINE",          type=inkex.Boolean, default=True)
        self.arg_parser.add_argument("--LWPOLYLINE",    type=inkex.Boolean, default=True)
        self.arg_parser.add_argument("--POINT",         type=inkex.Boolean, default=True)
        self.arg_parser.add_argument("--POLYLINE",      type=inkex.Boolean, default=True)
        self.arg_parser.add_argument("--POP_TRAFO",     type=inkex.Boolean, default=True)
        self.arg_parser.add_argument("--SEQEND",        type=inkex.Boolean, default=True)
        self.arg_parser.add_argument("--SOLID",         type=inkex.Boolean, default=True)
        self.arg_parser.add_argument("--SPLINE",        type=inkex.Boolean, default=True)
        self.arg_parser.add_argument("--TABLE",         type=inkex.Boolean, default=True)
        self.arg_parser.add_argument("--VERTEX",        type=inkex.Boolean, default=True)
        self.arg_parser.add_argument("--VIEWPORT",      type=inkex.Boolean, default=True)
        
        #other entities
        self.arg_parser.add_argument("--THREE_DSOLID",  type=inkex.Boolean, default=True) #3DSOLID
        self.arg_parser.add_argument("--ATTRIB",        type=inkex.Boolean, default=True)
        self.arg_parser.add_argument("--BODY",          type=inkex.Boolean, default=True)
        self.arg_parser.add_argument("--ARC_DIMENSION", type=inkex.Boolean, default=True)
        self.arg_parser.add_argument("--HATCH",         type=inkex.Boolean, default=True)
        self.arg_parser.add_argument("--IMAGE",         type=inkex.Boolean, default=True)
        self.arg_parser.add_argument("--INSERT",        type=inkex.Boolean, default=True)
        self.arg_parser.add_argument("--MESH",          type=inkex.Boolean, default=True)
        self.arg_parser.add_argument("--MTEXT",         type=inkex.Boolean, default=True)
        self.arg_parser.add_argument("--RAY",           type=inkex.Boolean, default=True)
        self.arg_parser.add_argument("--REGION",        type=inkex.Boolean, default=True)
        self.arg_parser.add_argument("--SHAPE",         type=inkex.Boolean, default=True)
        self.arg_parser.add_argument("--SURFACE",       type=inkex.Boolean, default=True)
        self.arg_parser.add_argument("--TRACE",         type=inkex.Boolean, default=True)
        self.arg_parser.add_argument("--UNDERLAY",      type=inkex.Boolean, default=True)
        self.arg_parser.add_argument("--XLINE",         type=inkex.Boolean, default=True)
        
    def openExplorer(self, temp_output_dir):
        if os.name == 'nt':
            subprocess.Popen(["explorer",temp_output_dir], close_fds=True)
        else:
            subprocess.Popen(["xdg-open",temp_output_dir], close_fds=True)
        
    def effect(self):
        #get input file and copy it to some new temporary directory
        inputfile = self.options.inputfile
        if not os.path.exists(inputfile):
            inkex.utils.debug("The input file does not exist. Please select a *.dxf or *.dwg file and try again.")
            exit(1)
        temp_input_dir = os.path.join(tempfile.gettempdir(),"dxfdwg_input") 
        shutil.rmtree(temp_input_dir, ignore_errors=True) #remove the input directory before doing new job
        if not os.path.exists(temp_input_dir):
            os.mkdir(temp_input_dir) #recreate blank dir
        shutil.copy2(inputfile, os.path.join(temp_input_dir, Path(inputfile).name)) # complete target filename given
        
        #Prepapre output conversion
        outputfilebase = os.path.splitext(os.path.basename(inputfile))[0]
        inputfile_ending = os.path.splitext(os.path.basename(inputfile))[1]
        temp_output_dir = os.path.join(tempfile.gettempdir(),"dxfdwg_output")
        shutil.rmtree(temp_output_dir, ignore_errors=True) #remove the output directory before doing new job
        if not os.path.exists(temp_output_dir):
            os.mkdir(temp_output_dir)
        
        #Prepare some more options for proceeding
        autocad_version = self.options.oda_outputformat.split("_")[0]
        autocad_format  = self.options.oda_outputformat.split("_")[1]
        self.options.oda_audit_repair = "1" if self.options.oda_audit_repair else "0" #overwrite string bool with int value
        entityspace = []
        if self.options.allentities or self.options.THREE_DFACE: entityspace.append("3DFACE")
        if self.options.allentities or self.options.ARC:           entityspace.append("ARC")
        if self.options.allentities or self.options.BLOCK:         entityspace.append("BLOCK")
        if self.options.allentities or self.options.CIRCLE:        entityspace.append("CIRCLE")
        if self.options.allentities or self.options.ELLIPSE:       entityspace.append("ELLIPSE")
        if self.options.allentities or self.options.LINE:          entityspace.append("LINE")
        if self.options.allentities or self.options.LWPOLYLINE:    entityspace.append("LWPOLYLINE")
        if self.options.allentities or self.options.POINT:         entityspace.append("POINT")
        if self.options.allentities or self.options.POLYLINE:      entityspace.append("POLYLINE")
        if self.options.allentities or self.options.POP_TRAFO:     entityspace.append("POP_TRAFO")
        if self.options.allentities or self.options.SEQEND:        entityspace.append("SEQEND")
        if self.options.allentities or self.options.SOLID:         entityspace.append("SOLID")
        if self.options.allentities or self.options.SPLINE:        entityspace.append("SPLINE")
        if self.options.allentities or self.options.TABLE:         entityspace.append("TABLE")
        if self.options.allentities or self.options.VERTEX:        entityspace.append("VERTEX")
        if self.options.allentities or self.options.VIEWPORT:      entityspace.append("VIEWPORT")
        
        if self.options.allentities or self.options.THREE_DSOLID:  entityspace.append("3DSOLID")
        if self.options.allentities or self.options.ATTRIB:        entityspace.append("ATTRIB")
        if self.options.allentities or self.options.BODY:          entityspace.append("BODY")
        if self.options.allentities or self.options.ARC_DIMENSION: entityspace.append("ARC_DIMENSION")
        if self.options.allentities or self.options.HATCH:         entityspace.append("HATCH")
        if self.options.allentities or self.options.IMAGE:         entityspace.append("IMAGE")
        if self.options.allentities or self.options.INSERT:        entityspace.append("INSERT")       
        if self.options.allentities or self.options.MESH:          entityspace.append("MESH")
        if self.options.allentities or self.options.MTEXT:         entityspace.append("MTEXT")
        if self.options.allentities or self.options.RAY:           entityspace.append("RAY")
        if self.options.allentities or self.options.REGION:        entityspace.append("REGION")
        if self.options.allentities or self.options.SHAPE:         entityspace.append("SHAPE")
        if self.options.allentities or self.options.SURFACE:       entityspace.append("SURFACE")
        if self.options.allentities or self.options.TRACE:         entityspace.append("TRACE")
        if self.options.allentities or self.options.UNDERLAY:      entityspace.append("UNDERLAY")
        if self.options.allentities or self.options.XLINE:         entityspace.append("XLINE")  
        
        #ODA to ezdxf mapping
        oda_ezdxf_mapping = []
        oda_ezdxf_mapping.append(["ACAD9",   "R12",  "AC1004"]) #this mapping is not supported directly. so we use the lowest possible which is R12
        oda_ezdxf_mapping.append(["ACAD10",  "R12",  "AC1006"]) #this mapping is not supported directly. so we use the lowest possible which is R12
        oda_ezdxf_mapping.append(["ACAD12",  "R12",  "AC1009"])   
        oda_ezdxf_mapping.append(["ACAD13",  "R2000","AC1012"]) #R13 was overwritten by R2000 which points to AC1015 instead of AC1014 (see documentation)
        oda_ezdxf_mapping.append(["ACAD14",  "R2000","AC1014"]) #R14 was overwritten by R2000 which points to AC1015 instead of AC1014 (see documentation)
        oda_ezdxf_mapping.append(["ACAD2000","R2000","AC1015"])
        oda_ezdxf_mapping.append(["ACAD2004","R2004","AC1018"])
        oda_ezdxf_mapping.append(["ACAD2007","R2007","AC1021"])
        oda_ezdxf_mapping.append(["ACAD2010","R2010","AC1024"])
        oda_ezdxf_mapping.append(["ACAD2013","R2013","AC1027"])
        oda_ezdxf_mapping.append(["ACAD2018","R2018","AC1032"])
        
        ezdxf_autocad_format = None
        for oe in oda_ezdxf_mapping:
            if oe[0] == autocad_version: 
                ezdxf_autocad_format = oe[1]
                break
        if ezdxf_autocad_format is None:
            inkex.errormsg("ezdxf conversion format version unknown")    
       
        #Prepare DXF and SVG paths
        dxf_file = os.path.join(temp_output_dir, outputfilebase + ".dxf")
        svg_file = os.path.join(temp_output_dir, outputfilebase + ".svg")
    
        # Run ODA File Converter
        if self.options.oda_skip_dxf_to_dxf == False or inputfile_ending == ".dwg":
            # Executable test (check for proper configuration by checking mime type. Should return octet stream for a binary executable)
            if os.name == "nt" and "application/octet-stream" not in str(MimeTypes().guess_type(urllib.pathname2url(self.options.oda_fileconverter))):
                inkex.utils.debug("You selected to use ODA File Converter but it is not configured properly. Check for installation and path location or select 'Skip conversion from DXF to DXF'. You can download ODA Converter from 'https://www.opendesign.com/guestfiles/oda_file_converter'. You need to install it in order to use it.")
                exit(1)
            elif os.path.isfile(self.options.oda_fileconverter) == False:
                inkex.utils.debug("You selected to use ODA File Converter but it is not configured properly. Check for installation and path location or select 'Skip conversion from DXF to DXF'. You can download ODA Converter from 'https://www.opendesign.com/guestfiles/oda_file_converter'. You need to install it in order to use it.")
                exit(1)
            else:
                # Build and run ODA File Converter command
                oda_cmd = [self.options.oda_fileconverter, temp_input_dir, temp_output_dir, autocad_version, autocad_format, "0", self.options.oda_audit_repair]
                if os.name == 'nt' and  self.options.oda_hidewindow:
                        info = subprocess.STARTUPINFO() #hide the ODA File Converter window because it is annoying (does not work for Linux :-()
                        info.dwFlags = 1
                        info.wShowWindow = 0
                        proc = subprocess.Popen(oda_cmd, startupinfo=info, shell=False, stdout=PIPE, stderr=PIPE)
                else: 
                        proc = subprocess.Popen(oda_cmd, shell=False, stdout=PIPE, stderr=PIPE)
                stdout, stderr = proc.communicate()
                if proc.returncode != 0 or (len(stderr) > 0 and stderr != b"Quit (core dumped)\n"): 
                   inkex.utils.debug("ODAFileConverter failed: %d %s %s" % (proc.returncode, stdout, stderr))
                   if os.name != 'nt':
                       inkex.utils.debug("If the error message above contains a warning about wrong/missing Qt version please install the required version. You can get the installer from 'https://download.qt.io/archive/qt/'. Sadly you will need to create a free account to install. After installation please configure the shell script '/usr/bin/ODAFileConverter' to add a preceding line with content similar to 'LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/opt/Qt5.14.2/5.14.2/gcc_64/lib/'.")
                   exit(1)
            # check if ODA converted successfully. This is the case if no error file was created
            oda_errorfile = os.path.join(temp_output_dir, Path(inputfile).name + ".err")
            if os.path.exists(oda_errorfile):
                inkex.utils.debug("ODA File Converter failed to process the file. Cannot continue DXF/DWG import. The error message is:")
                errormessage = open(oda_errorfile, 'r')
                errorlines = errormessage.readlines() 
                for errorline in errorlines: 
                    inkex.utils.debug(errorline.strip())
                errormessage.close()
                exit(1)
        
        # Do some movings/copies of skipped or processed DXF
        if self.options.oda_skip_dxf_to_dxf: #if true we need to move the file to simulate "processed"
            shutil.move(os.path.join(temp_input_dir, Path(inputfile).name), os.path.join(temp_output_dir, Path(inputfile).name))

        if self.options.oda_keepconverted_dxf:
            shutil.copy2(dxf_file, os.path.join(os.path.dirname(inputfile), outputfilebase + "_oda.dxf")) # complete target filename given
            
        # Preprocessing DXF to DXF (entity filter) by using ezdxf the first time
        if self.options.ezdxf_preprocessing:
            # uniconverter does not handle all entities. we parse the file to exlude stuff which lets uniconverter fail
            dxf = ezdxf.readfile(dxf_file)
            modelspace = dxf.modelspace()
            allowed_entities = []
            # supported entities by UniConverter- impossible: MTEXT TEXT INSERT and a lot of others
            query_string = str(entityspace)[1:-1].replace("'","").replace(",","")
            if query_string != "":
                for e in modelspace.query(query_string):
                    allowed_entities.append(e)
            #inkex.utils.debug(ezdxf_autocad_format)
            #inkex.utils.debug(self.options.ezdxf_output_version)
            if self.options.ezdxf_output_version == "SAME":                
                doc = ezdxf.new(ezdxf_autocad_format)
            else:
                doc = ezdxf.new(self.options.ezdxf_output_version) #use the string values from inx file. Required to match the values from ezdxf library. See Python reference
            msp = doc.modelspace()
            for e in allowed_entities:
                msp.add_foreign_entity(e)
            doc.saveas(dxf_file)
            if self.options.ezdfx_keep_preprocessed:
                shutil.copy2(dxf_file, os.path.join(os.path.dirname(inputfile), outputfilebase + "_ezdxf.dxf")) # complete target filename given
        
        # Make SVG from DXF
        if self.options.dxf_to_svg_parser == "sk1":         
            if os.name != "nt":
                inkex.utils.debug("You selected sk1 UniConvertor but you are not running on a Windows platform. On Linux uniconverter 1.1.X can be installed using the now obsolete Python 2.7, but it will not run correctly because you finally will fail at installing liblcms1-dev library on newer systems. That leads to uncompilable sk1libs package. Unfortunately sk1 UniConvertor 2.X does not support dxf format. So please use another DXF to SVG converter.")
                exit(1)
            sk1_command_ending = os.path.splitext(os.path.splitext(os.path.basename(self.options.sk1_uniconverter))[1])[0]
            if sk1_command_ending != ".cmd":
                inkex.utils.debug("You selected sk1 UniConverter but it was not configured properly. Check the path to the executable.")
                exit(1)
            uniconverter_cmd = [self.options.sk1_uniconverter, dxf_file, svg_file]
            #inkex.utils.debug(uniconverter_cmd)
            proc = subprocess.Popen(uniconverter_cmd, shell=False, stdout=PIPE, stderr=PIPE)
            stdout, stderr = proc.communicate()
            if proc.returncode != 0: 
               inkex.errormsg("UniConverter failed: %d %s %s" % (proc.returncode, stdout, stderr))
               if self.options.opendironerror:
                   self.openExplorer(temp_output_dir)
                                    
        elif self.options.dxf_to_svg_parser == "bjnortier":
            if which("node") is None:
                inkex.utils.debug("NodeJS executable not found on path. Please check your installation.")
                exit(1)
            else:
                bjnortier_cmd = ["node", os.path.join("node_modules","dxf","lib","cli.js"), dxf_file, svg_file]
                #inkex.utils.debug(bjnortier_cmd)
                proc = subprocess.Popen(bjnortier_cmd, shell=False, stdout=PIPE, stderr=PIPE)
                stdout, stderr = proc.communicate()
                if proc.returncode != 0: 
                   inkex.errormsg("node.js DXF to SVG conversion failed: %d %s %s" % (proc.returncode, stdout, stderr))
                   if self.options.opendironerror:
                       self.openExplorer(temp_output_dir)
                       
        elif self.options.dxf_to_svg_parser == "kabeja":         
            wd = os.path.join(os.getcwd(), "kabeja")
            #inkex.utils.debug(wd)
            proc = subprocess.Popen("java -jar launcher.jar -nogui -pipeline svg " + dxf_file + " " + svg_file, cwd=wd, shell=True, stdout=PIPE, stderr=PIPE)
            stdout, stderr = proc.communicate()
            if proc.returncode != 0: 
               inkex.errormsg("kabeja failed: %d %s %s" % (proc.returncode, stdout, stderr))  
               if self.options.opendironerror:
                   self.openExplorer(temp_output_dir)
        
        elif self.options.dxf_to_svg_parser == "vpype_dxf":
            try:
                from inkex.command import inkscape
                import vpype
                from vpype_cli import execute
            except Exception as e:
                inkex.errormsg("Error importing vpype. Did you properly install the vpype and vpype-dxf python modules?")
                exit(1)
            doc = vpype.Document() #create new vpype document
            command = "dread  --quantization " + str(self.options.vpype_quantization)
            if self.options.vpype_simplify is True:     
                command += " --simplify"
            if self.options.vpype_parallel is True:     
                command += " --parallel"     
            #command += " '" + inputfile + "'"
            command += " '" + dxf_file + "'"
                
            #inkex.errormsg(command)   
            doc = execute(command, doc)
            if doc.length() == 0:
                inkex.errormsg('No lines left after vpype conversion. Conversion result is empty. Cannot continue')
                exit(1)
            # save the vpype document to new svg file and close it afterwards
            output_fileIO = open(svg_file, "w", encoding="utf-8")
            vpype.write_svg(output_fileIO, doc, page_size=None, center=False, source_string='', layer_label_format='%d', show_pen_up=False, color_mode='layer')       
            output_fileIO.close()
            # convert vpype polylines/lines/polygons to regular paths again. We need to use "--with-gui" to respond to "WARNING: ignoring verb FileSave - GUI required for this verb."
            cli_output = inkscape(svg_file, "--with-gui", actions="EditSelectAllInAllLayers;EditUnlinkClone;ObjectToPath;FileSave;FileQuit")
            if len(cli_output) > 0:
                self.debug(_("Inkscape returned the following output when trying to run the vpype object to path back-conversion:"))
                self.debug(cli_output)
              
        elif self.options.dxf_to_svg_parser == "ezdxf":       
            try:
                doc = ezdxf.readfile(dxf_file)           
                msp = doc.modelspace()
                #for e in msp: #loop through entities
                #    inkex.errormsg(e)
                #doc.header['$DIMSCALE'] = 0.2 does not apply to the plot :-(
                #inkex.utils.debug(doc.header['$DIMSCALE'])
                #inkex.utils.debug(doc.header['$MEASUREMENT'])
                auditor = doc.audit() #audit & repair DXF document before rendering
                # The auditor.errors attribute stores severe errors, which *may* raise exceptions when rendering.
                if len(auditor.errors) == 0:
                    fig = plt.figure()
                    ax = plt.axes([0., 0., 1., 1.], xticks=[], yticks=[])
                    #ax = plt.axes([0., 0., 1., 1.], frameon=False, xticks=[], yticks=[])
                    ax.patches = []
                    #plt.axis('off')
                    plt.margins(0, 0)
                    plt.gca().xaxis.set_major_locator(plt.NullLocator())
                    plt.gca().yaxis.set_major_locator(plt.NullLocator())
                    plt.subplots_adjust(top=1, bottom=0, right=1, left=0, hspace=0, wspace=0)
                    out = MatplotlibBackend(fig.add_axes(ax))
                    Frontend(RenderContext(doc), out).draw_layout(msp, finalize=True)
                    #plt.show()
                    #fig.savefig(os.path.join(temp_output_dir, outputfilebase + ".png"), dpi=300)  
                    fig.savefig(svg_file) #see https://matplotlib.org/3.1.1/api/_as_gen/matplotlib.pyplot.savefig.html
            except IOError:
                inkex.errormsg("Not a DXF file or a generic I/O error.")
                exit(1)
            except ezdxf.DXFStructureError:
                inkex.errormsg("Invalid or corrupted DXF file.")
                exit(1)
            
        elif self.options.dxf_to_svg_parser == "legacy":
            inkex.utils.debug("The selected legacy DXF to SVG parser is not supported by this extension yet. Use File > Import > *.dxf. This calls the \"dxf_input.inx\" extension.")
            exit(1)
        else:
            inkex.utils.debug("undefined parser")
            exit(1)
        
        # Write the generated SVG into InkScape's canvas
        try:
            stream = open(svg_file, 'r')
        except FileNotFoundError as e:
            inkex.utils.debug("There was no SVG output generated. Cannot continue")
            exit(1)
        p = etree.XMLParser(huge_tree=True)
        doc = etree.parse(stream, parser=etree.XMLParser(huge_tree=True)).getroot()
        stream.close()
        doc.set('id', self.svg.get_unique_id("dxf_dwg_import-" + self.options.dxf_to_svg_parser + "-"))
        self.document.getroot().append(doc)

        #get children of the doc and move them one group above - we don't do this for bjnortier tool because this has different structure which we don't want to disturb
        if self.options.dxf_to_svg_parser == "sk1":
            elements = []
            emptyGroup = None
            for firstGroup in doc.getchildren():
                emptyGroup = firstGroup
                for element in firstGroup.getchildren():
                    elements.append(element)
                #break #only one cycle - could be bad idea or not                
            for element in elements:
                doc.set('id', self.svg.get_unique_id('dxf_dwg_import'))
                doc.insert(doc.index(firstGroup), element)
            
            if emptyGroup is not None:
                 emptyGroup.getparent().remove(emptyGroup)
             
        #empty the following vals because they destroy the size aspects of the import / make viewbox looking wrong       
        if self.options.dxf_to_svg_parser == "bjnortier" or self.options.dxf_to_svg_parser == "kabeja":        
            doc.set('width','')
            doc.set('height','')
            doc.set('viewBox','')
            doc.getchildren()[0].set('transform','')
            
        #adjust viewport and width/height to have the import at the center of the canvas
        if self.options.resizetoimport: 
            bbox = inkex.elements._selected.ElementList.bounding_box(doc.getchildren()[0])
            if bbox is not None:
                root = self.svg.getElement('//svg:svg');
                offset = self.svg.unittouu(str(self.options.extraborder) + self.options.extraborder_units)
                root.set('viewBox', '%f %f %f %f' % (bbox.left - offset, bbox.top - offset, bbox.width + 2 * offset, bbox.height + 2 * offset))
                root.set('width', bbox.width + 2 * offset)
                root.set('height', bbox.height + 2 * offset)
        
if __name__ == '__main__':
    DXFDWGImport().run()
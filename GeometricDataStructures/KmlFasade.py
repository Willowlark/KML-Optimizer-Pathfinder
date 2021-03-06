from lxml import etree, objectify
from GeometricDataStructures.Geometrics import *
from pykml.factory import KML_ElementMaker as KML
import re
import os

debug = 0


class KmlFasade(object):

    def __init__(self, path):
        """
        `Author`: Bill Clark

        This object wraps an lxml object and makes it easy to worth with. This is designed for quick, useful
        functionality that ignores irrelevant carry over data. It provides function to return list of useful
        xml data, tools to apply changes to the xml file based on the objects it generates, and other features.

        `path`: Path of the source file.
        """

        self.filepath = path
        self.placemarks = None
        self.garbage = []
        self.geometrics = None
        self.additionfolder = None

        #Before we open the file as a kml object, we need to open it
        # as a regular file and remove the namspace on the file. Otherwise searching will fail.
        file = open(path, 'r')
        lines = file.readlines()
        file.close()

        for i in xrange(len(lines)):
            if re.search("<kml xmlns=.*", lines[i]) is not None: #Found the namespace line, remove it and rewrite.
                lines[i] = "<kml>\n"
                file = open(path, 'w')
                file.writelines(lines)
                file.close()
                break
            elif re.search("<kml>[\s]*", lines[1]) is not None: #A no namespace line was found, break out of the loop.
                break

        self.kmlTree = etree.parse(path)
        self.kmlRoot = self.kmlTree.getroot()


    def rewrite(self, path=None):
        """
        `Author`: Bill Clark

        Writes the stored file object back to the orginal file or a provided path.

        `path`: The path to write to, otherwise it will use the original write path.
        """

        if path == None:
            f = open(self.filepath, 'w')
            #f.write(elementPrint(self.kmlRoot))
            self.kmlTree.write(f, pretty_print=True)
            f.close()
        else:
            f = open(path, 'w')
            #f.write(elementPrint(self.kmlRoot))
            self.kmlTree.write(f, pretty_print=True)
            f.close()

    def removeGarbageTags(self):
        """
        `Author`: Bill Clark

        This method is a catch all for and garbage filtering operations. Currently it has one functionality,
        it takes every element stored in the garbage field and removes it from the Kml. Each element in the garbage
        list has no relevent data, removing it helps with the file length.
        """

        for element in self.garbage:
            parent = element.getparent()
            parent.remove(element)

    def pullPlacemarksAndGarbage(self):
        """
        `Author`: Bill Clark

        This method is used to append any xml tag with the placemark tag to a list and return it.
        As the most relevant data in a kml file appears in a placemark tag, this is a convience operation
        to prevent excess searching.
        During the interation, the method also looks to find all elements in the file that are irrelevant.
        Each element with it's tag in garbage data has no geometric data we care about. We can freely
        delete them later with the garbageFilter method. The functions are done at the same time for
        efficiency's sake, we have very large files to process.

        `return`: A list of lxml Element objects matching the placemark tag. This is also stored in class.
        """

        garbageData = ["styleUrl", 'Style', 'LookAt', 'visibility', 'Snippet',
                       'ScreenOverlay', 'tessellate', 'altitudeMode', 'extrude', 'TimeSpan']
        ret = []
        for x in self.kmlRoot.iter():
            if x.tag == 'Placemark':
                if debug: print x.tag, x.text
                ret.append(x)
            elif x.tag in garbageData:
                self.garbage.append(x)
        # self.placemarks = ret
        return ret

    def processPlacemarks(self, extract=0, geos=1):
        """
        `Author`: Bill Clark, Nick LaPosta

        This method iterates through the placemarks of the kml file. It has two functional purposes, primary being
        the convertion to geometrics. Geometrics are necessary to process, clip, and modify coordinate data. The
        second functionality is to pull out any data contained in the name and description fields. This data is
        stored in the Outputs\metadata folder for later access. Both functions are done within a single iteration
        of the placemarks for efficiency.

        `extract`: flag to turn on the HTML metadata extraction function of the loop. Defaults to off.

        `geos`: flag to turn on the geometric conversion part of the loop. Defaults to on.

        `return`: List of geometric objects for each placemark in this object's placemark list. This is stored in class
                  as well.
        """

        if(self.placemarks is None):
            placemarks = self.pullPlacemarksAndGarbage()

        factory = GeometricFactory()
        ret = []
        skip = 0

        if extract:
            directory = "Outputs\Metadata\\" + os.path.basename(self.filepath)[:-3]
            if not os.path.exists(directory):
                os.mkdir(directory)

        for place in placemarks:
            for element in place.iter():

                if extract:
                    if element.tag == "name":
                        filename = element.text
                        output = open(directory + "\\" + filename, 'a')
                        output.write(self.html_entry("h1", element.tag, element.text))
                        output.close()
                    elif element.tag == "description":
                        output = open(directory + "\\" + filename, 'a')
                        output.write(self.html_entry("h2", element.tag, element.text))
                        output.close()

                if geos:
                    if skip:
                        skip += len(element)
                        skip-=1

                    elif element.tag in factory.geometryTypes:
                        geo = factory.create(element)
                        assert geo is not None  # Checking an object actually got made.

                        if type(geo) is list: ret.extend(geo)  # catches multigeometry returns.
                        else: ret.append(geo)

                        if element.tag == "Polygon" or element.tag == "MultiGeometry": skip = len(element)
                    else:
                        pass
        self.geometrics = ret
        return ret

    def html_entry(self, html_tag, tag, text):
        """
        `Author`: Nick Laposta

        Formats a string to an html entry for logging purposes. Used by the processPlacemarks when extract is set to 1.

        `html_tag`: The html style tag to be used.

        `tag`: The tag of the xml element being logged.

        `text`: The text value of the xml element.

        `return`: A formatted html string of the tag and text.
        """
        return "<" + html_tag + ">" + tag + "</" + html_tag + ">" + "\n\n" + text + "\n\n"

    def fasadeUpdate(self):
        """
        `Author`: Bill Clark

        Runs the applyedit function on every geometric object contained in this objects geometric's list.
        If the addition folder has been generated, This method will also add that folder to the file.
        """

        for element in self.geometrics:
            element.applyEdits()
        self.geometrics = [e for e in self.geometrics if not e.remove == len(e.coordinates)]

        if self.additionfolder is not None:
            for x in self.kmlRoot.iter():
                if x.tag == "Document":
                    x.append(self.additionfolder)
                    break

    def createAdditionsFolder(self):
        """
        `Author`: Bill Clark

        Initializes the kml folder any additional points will be written to. Simple kml container.

        `return`: Nothing.
        """
        fld = KML.Folder(KML.name("Additions"))
        self.additionfolder = fld

    def createAdditionalGeometry(self, type, name='blank', coordin='0,0'):
        """
        `Author`: Bill Clark

        This method allows for a user to create new point, linestrings, and linearrings. It will default the
        name and coordinates for the object if they aren't provided, but every call requires a type, one of the
        above three. This method appends the created kml to the additions folder which needs to be produced beforehand.

        `type`: String, reading Point, LineString, or LinearRing.

        `name`: The name tag for the element. Simply for identification. Must be a String.

        `coordin`: The coordinates for the kml. Must be a String.

        `return`:
        """

        if type == "Point":
            pm1 = KML.Placemark(KML.name(name),KML.Point(KML.coordinates(coordin)))

        elif type == "LineString":
            pm1 = KML.Placemark(KML.name(name),KML.LineString(KML.coordinates(coordin)))

        elif type == "LinearRing":
            pm1 = KML.Placemark(KML.name(name),KML.LinearRing(KML.coordinates(coordin)))
        else:
            print 'Derp.'

        self.additionfolder.append(pm1)

    def yieldGeometrics(self):
        """
        `Author`: Bill Clark

        Returns the geometrics contained in the class. Needed for implementations using
        the composite module. It uses yield instead of return so that it can be accessed in the same way of the
        composite, for x in yield.
        """
        yield self.geometrics

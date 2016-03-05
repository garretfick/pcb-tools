
from .render import GerberContext
from ..am_statements import *
from ..gerber_statements import *
from ..primitives import AMGroup, Arc, Circle, Line, Outline, Rectangle
from copy import deepcopy

class AMGroupContext(object):
    '''A special renderer to generate aperature macros from an AMGroup'''
    
    def __init__(self):
        self.statements = []
    
    def render(self, amgroup, name):
        
        # Clone ourselves, then offset by the psotion so that
        # our render doesn't have to consider offset. Just makes things simplder
        nooffset_group = deepcopy(amgroup)
        nooffset_group.position = (0, 0)
        
        # Now draw the shapes
        for primitive in nooffset_group.primitives:
            if isinstance(primitive, Outline):
                self._render_outline(primitive)
            elif isinstance(primitive, Circle):
                self._render_circle(primitive)
            elif isinstance(primitive, Rectangle):
                self._render_rectangle(primitive)
            elif isinstance(primitive, Line):
                self._render_line(primitive)
            else:
                raise ValueError('amgroup')

        statement = AMParamStmt('AM', name, self._statements_to_string())
        return statement
    
    def _statements_to_string(self):
        macro = ''

        for statement in self.statements:
            macro += statement.to_gerber()
            
        return macro
    
    def _render_circle(self, circle):
        self.statements.append(AMCirclePrimitive.from_primitive(circle))
        
    def _render_rectangle(self, rectangle):
        self.statements.append(AMCenterLinePrimitive.from_primitive(rectangle))
        
    def _render_line(self, line):
        self.statements.append(AMVectorLinePrimitive.from_primitive(line))
     
    def _render_outline(self, outline):
        self.statements.append(AMOutlinePrimitive.from_primitive(outline))
    
    def _render_thermal(self, thermal):
        pass
    

class Rs274xContext(GerberContext):
    
    def __init__(self, settings):
        GerberContext.__init__(self)
        self.comments = []
        self.header = []
        self.body = []
        self.end = [EofStmt()]
        
        # Current values so we know if we have to execute
        # moves, levey changes before anything else
        self._level_polarity = None
        self._pos = (None, None)
        self._func = None
        self._quadrant_mode = None
        self._dcode = None
        
        self._next_dcode = 10
        self._rects = {}
        self._circles = {}
        self._obrounds = {}
        self._polygons = {}
        self._macros = {}
        
        self._i_none = 0
        self._j_none = 0
        
        self.settings = settings

        self._start_header(settings)
        #self._define_dcodes()
        
    def _start_header(self, settings):
        self.header.append(FSParamStmt.from_settings(settings))
        self.header.append(MOParamStmt.from_units(settings.units))
        
    def _define_dcodes(self):
        
        self._get_circle(.1575, 10)
        self._get_circle(.035, 17)
        self._get_rectangle(0.1575, 0.1181, 15)
        self._get_rectangle(0.0492, 0.0118, 16)
        self._get_circle(.0197, 11)
        self._get_rectangle(0.0236, 0.0591, 12)
        self._get_circle(.005, 18)
        self._get_circle(.008, 19)
        self._get_circle(.009, 20)
        self._get_circle(.01, 21)
        self._get_circle(.02, 22)
        self._get_circle(.006, 23)
        self._get_circle(.015, 24)
        self._get_rectangle(0.1678, 0.1284, 26)
        self._get_rectangle(0.0338, 0.0694, 25)
        
    def _simplify_point(self, point):
        return (point[0] if point[0] != self._pos[0] else None, point[1] if point[1] != self._pos[1] else None)
    
    def _simplify_offset(self, point, offset):
        
        if point[0] != offset[0]:
            xoffset = point[0] - offset[0]
        else:
            xoffset = self._i_none
            
        if point[1] != offset[1]:
            yoffset = point[1] - offset[1]
        else:
            yoffset = self._j_none
        
        return (xoffset, yoffset)
        
    @property
    def statements(self):
        return self.comments + self.header + self.body + self.end
        
    def set_bounds(self, bounds):
        pass
    
    def _paint_background(self):
        pass
    
    def _select_aperture(self, aperture):
        
        # Select the right aperture if not already selected
        if aperture:
            if isinstance(aperture, Circle):
                aper = self._get_circle(aperture.diameter)
            elif isinstance(aperture, Rectangle):
                aper = self._get_rectangle(aperture.width, aperture.height)
            else:
                raise NotImplementedError('Line with invalid aperture type')
                
            if aper.d != self._dcode:
                self.body.append(ApertureStmt(aper.d))
                self._dcode = aper.d
        
    def _render_line(self, line, color):
        
        self._select_aperture(line.aperture)
        
        self._render_level_polarity(line)
            
        # Get the right function
        if self._func != CoordStmt.FUNC_LINEAR:
            func = CoordStmt.FUNC_LINEAR
        else:
            func = None
        self._func = CoordStmt.FUNC_LINEAR
        
        if self._pos != line.start:
            self.body.append(CoordStmt.move(func, self._simplify_point(line.start)))
            self._pos = line.start
            # We already set the function, so the next command doesn't require that
            func = None
        
        point = self._simplify_point(line.end)
        
        # In some files, we see a lot of duplicated ponts, so omit those
        if point[0] != None or point[1] != None:
            self.body.append(CoordStmt.line(func, self._simplify_point(line.end)))
            self._pos = line.end
        
    def _render_arc(self, arc, color):
        
        # Optionally set the quadrant mode if it has changed:
        if arc.quadrant_mode != self._quadrant_mode:
            
            if arc.quadrant_mode != 'multi-quadrant':
                self.body.append(QuadrantModeStmt.single())
            else:
                self.body.append(QuadrantModeStmt.multi())
            
            self._quadrant_mode = arc.quadrant_mode
            
        # Select the right aperture if not already selected
        self._select_aperture(arc.aperture)
        
        self._render_level_polarity(arc)
        
        # Find the right movement mode. Always set to be sure it is really right
        dir = arc.direction
        if dir == 'clockwise':
            func = CoordStmt.FUNC_ARC_CW
            self._func = CoordStmt.FUNC_ARC_CW
        elif dir == 'counterclockwise':
            func = CoordStmt.FUNC_ARC_CCW
            self._func = CoordStmt.FUNC_ARC_CCW
        else:
            raise ValueError('Invalid circular interpolation mode')
            
        if self._pos != arc.start:
            # TODO I'm not sure if this is right
            self.body.append(CoordStmt.move(CoordStmt.FUNC_LINEAR, self._simplify_point(arc.start)))
            self._pos = arc.start
            
        center = self._simplify_offset(arc.center, arc.start)
        end = self._simplify_point(arc.end)
        self.body.append(CoordStmt.arc(func, end, center))
        self._pos = arc.end

    def _render_region(self, region, color):
        
        self._render_level_polarity(region)
        
        self.body.append(RegionModeStmt.on())
        
        for p in region.primitives:
            
            if isinstance(p, Line):
                self._render_line(p, color)
            else:
                self._render_arc(p, color)
                

        self.body.append(RegionModeStmt.off())
        
    def _render_level_polarity(self, region):
        if region.level_polarity != self._level_polarity:
            self._level_polarity = region.level_polarity
            self.body.append(LPParamStmt.from_region(region))
            
    def _render_flash(self, primitive, aperture):
        
        if aperture.d != self._dcode:
            self.body.append(ApertureStmt(aperture.d))
            self._dcode = aperture.d
        
        self.body.append(CoordStmt.flash( self._simplify_point(primitive.position)))
        self._pos = primitive.position
            
    def _get_circle(self, diameter, dcode = None):
        '''Define a circlar aperture'''
        
        aper = self._circles.get(diameter, None)

        if not aper:
            if not dcode:
                dcode = self._next_dcode
                self._next_dcode += 1
            else:
                self._next_dcode = max(dcode + 1, self._next_dcode)
                
            aper = ADParamStmt.circle(dcode, diameter)
            self._circles[diameter] = aper
            self.header.append(aper)

        return aper
        
    def _render_circle(self, circle, color):

        aper = self._get_circle(circle.diameter)
        self._render_flash(circle, aper)

    def _get_rectangle(self, width, height, dcode = None):
        '''Get a rectanglar aperture. If it isn't defined, create it'''
        
        key = (width, height)
        aper = self._rects.get(key, None)
        
        if not aper:
            if not dcode:
                dcode = self._next_dcode
                self._next_dcode += 1
            else:
                self._next_dcode = max(dcode + 1, self._next_dcode)
            
            aper = ADParamStmt.rect(dcode, width, height)
            self._rects[(width, height)] = aper
            self.header.append(aper)
    
        return aper

    def _render_rectangle(self, rectangle, color):
        
        aper = self._get_rectangle(rectangle.width, rectangle.height)
        self._render_flash(rectangle, aper)
        
    def _get_obround(self, width, height, dcode = None):
        
        key = (width, height)
        aper = self._obrounds.get(key, None)
        
        if not aper:
            if not dcode:
                dcode = self._next_dcode
                self._next_dcode += 1
            else:
                self._next_dcode = max(dcode + 1, self._next_dcode)
            
            aper = ADParamStmt.obround(dcode, width, height)
            self._obrounds[(width, height)] = aper
            self.header.append(aper)
    
        return aper
        
    def _render_obround(self, obround, color):
        
        aper = self._get_obround(obround.width, obround.height)
        self._render_flash(obround, aper)
        
        pass
        
    def _render_polygon(self, polygon, color):
        raise NotImplementedError('Not implemented yet')
        pass
        
    def _render_drill(self, circle, color):
        pass
    
    def _hash_amacro(self, amgroup):
        '''Calculate a very quick hash code for deciding if we should even check AM groups for comparision'''
        
        hash = ''
        for primitive in amgroup.primitives:
            
            hash += primitive.__class__.__name__[0]
            
            bbox = primitive.bounding_box
            hash += str((bbox[0][1] - bbox[0][0]) * 100000)[0:2]
            hash += str((bbox[1][1] - bbox[1][0]) * 100000)[0:2]
            
            if hasattr(primitive, 'primitives'):
                hash += str(len(primitive.primitives))
                
            if isinstance(primitive, Rectangle):
                hash += str(primitive.width * 1000000)[0:2]
                hash += str(primitive.height * 1000000)[0:2]
            elif isinstance(primitive, Circle):
                hash += str(primitive.diameter * 1000000)[0:2]
            
        return hash

    def _get_amacro(self, amgroup, dcode = None):
        # Macros are a little special since we don't have a good way to compare them quickly
        # but in most cases, this should work
        
        hash = self._hash_amacro(amgroup)
        macro = None
        macroinfo = self._macros.get(hash, None)
        
        if macroinfo:
            
            # We hae a definition, but check that the groups actually are the same
            for macro in macroinfo:
                offset = (amgroup.position[0] - macro[1].position[0], amgroup.position[1] - macro[1].position[1])
                if amgroup.equivalent(macro[1], offset):
                    break
                macro = None
                
        # Did we find one in the group0
        if not macro:
            # This is a new macro, so define it
            if not dcode:
                dcode = self._next_dcode
                self._next_dcode += 1
            else:
                self._next_dcode = max(dcode + 1, self._next_dcode)
            
            # Create the statements
            # TODO
            amrenderer = AMGroupContext()
            statement = amrenderer.render(amgroup, hash)
            
            self.header.append(statement)
            
            aperdef = ADParamStmt.macro(dcode, hash)
            self.header.append(aperdef)
            
            # Store the dcode and the original so we can check if it really is the same
            macro = (aperdef, amgroup)
            
            if macroinfo:
                macroinfo.append(macro)
            else:
                self._macros[hash] = [macro]                
            
        return macro[0]
        
    def _render_amgroup(self, amgroup, color):
        
        aper = self._get_amacro(amgroup)
        self._render_flash(amgroup, aper)

    def _render_inverted_layer(self):
        pass
        
    def post_render_primitives(self):
        '''No more primitives, so set the end marker'''
        
        self.body.append()
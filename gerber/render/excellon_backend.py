
from .render import GerberContext
from ..excellon_statements import *

class ExcellonContext(GerberContext):
    
    def __init__(self, settings):
        GerberContext.__init__(self)
        self.comments = []
        self.header = []
        self.tool_def = []
        self.body_start = [RewindStopStmt()]
        self.body = []
        self.start = [HeaderBeginStmt()]
        self.end = [EndOfProgramStmt()]
        
        self.handled_tools = set()
        self.cur_tool = None
        self._pos = (None, None)
        
        self.settings = settings

        self._start_header()
        self._start_comments()
        
    def _start_header(self):
        """Create the header from the settings"""
        
        self.header.append(UnitStmt.from_settings(self.settings))
        
    def _start_comments(self):
        
        # Write the digits used - this isn't valid Excellon statement, so we write as a comment
        self.comments.append(CommentStmt('FILE_FORMAT=%d:%d' % (self.settings.format[0], self.settings.format[1])))
        
    @property
    def statements(self):
        return self.start + self.comments + self.header + self.body_start + self.body + self.end
        
    def set_bounds(self, bounds):
        pass
    
    def _paint_background(self):
        pass
        
    def _render_line(self, line, color):
        raise ValueError('Invalid Excellon object')
    def _render_arc(self, arc, color):
        raise ValueError('Invalid Excellon object')

    def _render_region(self, region, color):
        raise ValueError('Invalid Excellon object')
        
    def _render_level_polarity(self, region):
        raise ValueError('Invalid Excellon object')

    def _render_circle(self, circle, color):
        raise ValueError('Invalid Excellon object')

    def _render_rectangle(self, rectangle, color):
        raise ValueError('Invalid Excellon object')
        
    def _render_obround(self, obround, color):
        raise ValueError('Invalid Excellon object')
        
    def _render_polygon(self, polygon, color):
        raise ValueError('Invalid Excellon object')
    
    def _simplify_point(self, point):
        return (point[0] if point[0] != self._pos[0] else None, point[1] if point[1] != self._pos[1] else None)

    def _render_drill(self, drill, color):
        
        tool = drill.hit.tool
        if not tool in self.handled_tools:
            self.handled_tools.add(tool)
            self.header.append(ExcellonTool.from_tool(tool))
    
        if tool != self.cur_tool:
            self.body.append(ToolSelectionStmt(tool.number))
            self.cur_tool = tool
            
        point = self._simplify_point(drill.position)
        self._pos = drill.position
        self.body.append(CoordinateStmt.from_point(point))
        
    def _render_slot(self, slot, color):
        
        tool = slot.hit.tool
        if not tool in self.handled_tools:
            self.handled_tools.add(tool)
            self.header.append(ExcellonTool.from_tool(tool))
    
        if tool != self.cur_tool:
            self.body.append(ToolSelectionStmt(tool.number))
            self.cur_tool = tool
            
        # Slots don't use simplified points
        self._pos = slot.end
        self.body.append(SlotStmt.from_points(slot.start, slot.end))

    def _render_inverted_layer(self):
        pass
        
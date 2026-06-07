from webthing import ( Property, Thing, Value)
from device import WindowHandle
import tornado.ioloop


class WindowHandleWebThing(Thing):

    # regarding capabilities refer https://iot.mozilla.org/schemas
    # there is also another schema registry http://iotschema.org/docs/full.html not used by webthing

    def __init__(self, description: str, device: WindowHandle):
        Thing.__init__(
            self,
            'urn:dev:ops:window-handle-1',
            'WindowHandle ' + device.name,
            ['MultiLevelSensor'],
            description
        )

        self.ioloop = tornado.ioloop.IOLoop.current()
        self.device = device
        self.device.register_listener(self.on_updated)

        self.name = Value(self.device.name)
        self.add_property(
            Property(self,
                     'name',
                     self.name,
                     metadata={
                         'title': 'name',
                         "type": "string",
                         'description': '"The name',
                         'readOnly': True,
                     }))

        self.eepid = Value(self.device.eep_id)
        self.add_property(
            Property(self,
                     'eep_id',
                     self.eepid,
                     metadata={
                         'title': 'eep id',
                         "type": "string",
                         'description': '"The eep id',
                         'readOnly': True,
                     }))

        self.enoceanid = Value(self.device.sender)
        self.add_property(
            Property(self,
                     'enocean_id',
                     self.enoceanid,
                     metadata={
                         'title': 'enocean id',
                         "type": "string",
                         'description': '"The enocean id',
                         'readOnly': True,
                     }))

        self.state = Value(self.device.state)
        self.add_property(
            Property(self,
                     'state',
                     self.state,
                     metadata={
                         'title': 'State',
                         "type": "integer",
                         'description': 'The state of the handle',
                         'readOnly': True,
                     }))

        self.state_text = Value(self.device.state_text)
        self.add_property(
            Property(self,
                     'state_text',
                     self.state_text,
                     metadata={
                         'title': 'State Description',
                         "type": "string",
                         'description': 'The state description',
                         'readOnly': True,
                     }))

        self.closed = Value(self.device.closed)
        self.add_property(
            Property(self,
                     'closed',
                     self.closed,
                     metadata={
                         'title': 'Closed state',
                         "type": "boolean",
                         'description': 'True, if closed',
                         'readOnly': True,
                     }))

    def on_updated(self, device: WindowHandle):
        self.ioloop.add_callback(self.__update_state, device)

    def __update_state(self, device: WindowHandle):
        self.state.notify_of_external_update(device.state)
        self.state_text.notify_of_external_update(device.state_text)
        self.closed.notify_of_external_update(device.closed)

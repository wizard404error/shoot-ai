// QWebChannel JavaScript library
// Compatible with PySide6 / Qt 6 QWebChannel
// Based on Qt's official qwebchannel.js

(function(global) {
    "use strict";

    function QWebChannel(transport, initCallback) {
        if (typeof transport !== "object" || typeof transport.send !== "function") {
            console.error("The QWebChannel transport is not a valid object or doesn't have a send method");
            return;
        }

        this.transport = transport;
        this.objects = {};
        this.objectNames = [];
        this.signals = {};

        var self = this;

        // Listen for messages from the transport
        transport.onmessage = function(message) {
            var data;
            try {
                if (typeof message === "string") {
                    data = JSON.parse(message);
                } else {
                    data = message;
                }
            } catch (e) {
                console.error("Failed to parse QWebChannel message:", e, message);
                return;
            }

            switch (data.type) {
                case "signal":
                    var object = self.objects[data.object];
                    if (object) {
                        var signal = object[data.signal];
                        if (typeof signal === "function") {
                            signal.apply(object, data.args || []);
                        } else if (object.__signals__ && object.__signals__[data.signal]) {
                            object.__signals__[data.signal].apply(object, data.args || []);
                        } else {
                            console.warn("Signal not found:", data.object, data.signal);
                        }
                    } else {
                        console.warn("Object not found for signal:", data.object);
                    }
                    break;

                case "response":
                    // Handle response to a method invocation
                    if (self._pendingCallbacks && self._pendingCallbacks[data.id]) {
                        var callback = self._pendingCallbacks[data.id];
                        delete self._pendingCallbacks[data.id];
                        if (data.error) {
                            if (callback.errorCallback) {
                                callback.errorCallback(data.error);
                            } else {
                                console.error("QWebChannel method error:", data.error);
                            }
                        } else {
                            if (callback.successCallback) {
                                callback.successCallback(data.result);
                            }
                        }
                    }
                    break;

                case "propertyUpdate":
                    var object = self.objects[data.object];
                    if (object) {
                        for (var i = 0; i < data.properties.length; i += 2) {
                            object[data.properties[i]] = data.properties[i + 1];
                        }
                    }
                    break;

                default:
                    console.warn("Unknown QWebChannel message type:", data.type, data);
            }
        };

        // Request initial object list
        this._sendMessage({type: "init"}, function(data) {
            if (data && data.objects) {
                for (var i = 0; i < data.objects.length; ++i) {
                    var name = data.objects[i];
                    self.objects[name] = {};
                    self.objectNames.push(name);
                }
                // Trigger any registered init callbacks
                if (self._initCallbacks) {
                    for (var j = 0; j < self._initCallbacks.length; j++) {
                        self._initCallbacks[j](self);
                    }
                }
            }
            if (initCallback) {
                initCallback(self);
            }
        });

        return this;
    }

    QWebChannel.prototype._sendMessage = function(message, callback) {
        var id = null;
        if (callback) {
            if (!this._pendingCallbacks) {
                this._pendingCallbacks = {};
            }
            id = QWebChannel._nextMessageId++;
            message.id = id;
            this._pendingCallbacks[id] = {successCallback: callback};
        }
        try {
            this.transport.send(JSON.stringify(message));
        } catch (e) {
            console.error("QWebChannel send failed:", e);
        }
    };

    QWebChannel.prototype.registerObject = function(name, object) {
        this.objects[name] = object;
        this.objectNames.push(name);
    };

    QWebChannel.prototype.exec = function(objectName, methodName, args, callback, errorCallback) {
        var message = {
            type: "invokeMethod",
            object: objectName,
            method: methodName,
            args: args || []
        };
        if (callback || errorCallback) {
            this._sendMessage(message, function(data) {
                if (callback) callback(data);
            });
            // Override the default callback to support error
            if (errorCallback && this._pendingCallbacks) {
                var callbacks = Object.values(this._pendingCallbacks);
                if (callbacks.length > 0) {
                    callbacks[callbacks.length - 1].errorCallback = errorCallback;
                }
            }
        } else {
            this._sendMessage(message);
        }
    };

    QWebChannel._nextMessageId = 1;

    global.QWebChannel = QWebChannel;
})(window);

// app.js - P2P Number Swarm Logic

// Assume IrcFramework is available globally (e.g. via a <script> tag for a browser bundle)
// For actual deployment, irc-framework would need to be properly included and bundled.
// const IrcFramework = require('irc-framework'); // Example if in Node.js or using a bundler
// Note: Firebase SDK script tags removed from index.html
// Note: Firebase configuration and initialization have been removed.

// -----------------------------------------------------------------------------
// DOM Element References
// -----------------------------------------------------------------------------
const localPeerIdDisplay = document.getElementById('local-peer-id');
const peerListUl = document.getElementById('peer-list');
const localNumberDisplay = document.getElementById('local-number-display');
const generateNumberBtn = document.getElementById('generate-number-btn');
const swarmMaxDisplay = document.getElementById('swarm-max-display');

// -----------------------------------------------------------------------------
// Global Variables
// -----------------------------------------------------------------------------
let localPeerId = null;
const peerConnections = {}; // Stores RTCPeerConnection objects, keyed by remotePeerId
const dataChannels = {};    // Stores RTCDataChannel objects, keyed by remotePeerId
let localNumber = null;
let swarmMaximum = null;
const connectedPeersNumbers = new Map(); // Stores numbers received from peers {peerId: number}
const ircPeers = new Map(); // Stores { nick: { peerId: '...', lastHello: timestamp } }
let peerTimeoutInterval = null;
let periodicHelloInterval = null;


// WebRTC Configuration
const STUN_SERVER = { 'iceServers': [{ 'urls': 'stun:stun.l.google.com:19302' }] };

// IRC Configuration using irc-framework style
const ircOptions = {
    host: "irc.libera.chat",
    port: 6697,
    ssl: true,
    nick: "peer_placeholder",
    username: "p2pswarm",
    gecos: "P2P Swarm Node",
    auto_reconnect: true,
    auto_reconnect_wait: 4000,
    auto_reconnect_max_retries: 3,
    mainChannel: null, // Will be set in initializeApp
    localPeerIdForNick: null
};
let ircClient = null;

// -----------------------------------------------------------------------------
// Utility Functions
// -----------------------------------------------------------------------------
function generatePeerId() {
    return `user-${Math.random().toString(36).substr(2, 9)}`;
}

function addPeerToUI(peerId) {
    if (!document.getElementById(`peer-${peerId}`)) {
        const listItem = document.createElement('li');
        listItem.id = `peer-${peerId}`;
        listItem.textContent = peerId;
        peerListUl.appendChild(listItem);
    }
}

function removePeerFromUI(peerId) {
    const listItem = document.getElementById(`peer-${peerId}`);
    if (listItem) {
        peerListUl.removeChild(listItem);
    }
}

// -----------------------------------------------------------------------------
// WebRTC Core Functions
// -----------------------------------------------------------------------------
function createPeerConnection(remotePeerId, isInitiator) {
    console.log(`Creating PeerConnection for ${remotePeerId}. Initiator: ${isInitiator}`);
    if (peerConnections[remotePeerId]) {
        console.warn(`PeerConnection for ${remotePeerId} already exists. Closing existing one.`);
        peerConnections[remotePeerId].close();
    }

    const pc = new RTCPeerConnection(STUN_SERVER);
    peerConnections[remotePeerId] = pc;

    pc.onicecandidate = (event) => {
        if (event.candidate) {
            let remoteNick = null;
            for (const [nick, data] of ircPeers.entries()) {
                if (data.peerId === remotePeerId) {
                    remoteNick = nick;
                    break;
                }
            }

            if (remoteNick && ircClient && ircClient.connected) {
                console.log(`Sending ICE candidate to ${remoteNick} (PeerID: ${remotePeerId})`);
                const candidateSignal = { type: "candidate", senderPeerId: localPeerId, data: event.candidate };
                ircClient.say(remoteNick, `WEBRTC_SIGNAL:${JSON.stringify(candidateSignal)}`);
            } else if (!remoteNick) {
                console.warn(`Cannot send ICE candidate: unknown IRC nick for peerId ${remotePeerId}.`);
            } else {
                console.warn(`Cannot send ICE candidate: IRC client not connected.`);
            }
        }
    };

    pc.onconnectionstatechange = () => {
        console.log(`Connection state with ${remotePeerId}: ${pc.connectionState}`);
        if (pc.connectionState === 'disconnected' || pc.connectionState === 'failed' || pc.connectionState === 'closed') {
            handleDisconnect(remotePeerId);
        } else if (pc.connectionState === 'connected') {
            addPeerToUI(remotePeerId);
            if (localNumber !== null) {
                sendNumberToPeer(remotePeerId, localNumber);
            }
        }
    };

    if (isInitiator) {
        console.log(`Creating DataChannel for ${remotePeerId}`);
        const sendChannel = pc.createDataChannel('sendDataChannel');
        setupDataChannel(sendChannel, remotePeerId);
        dataChannels[remotePeerId] = sendChannel;
    } else {
        pc.ondatachannel = (event) => {
            console.log(`Received DataChannel from ${remotePeerId}`);
            const receiveChannel = event.channel;
            setupDataChannel(receiveChannel, remotePeerId);
            dataChannels[remotePeerId] = receiveChannel;
        };
    }
    return pc;
}

function setupDataChannel(channel, remotePeerId) {
    channel.onopen = () => {
        console.log(`Data channel with ${remotePeerId} opened.`);
        addPeerToUI(remotePeerId);
        if (localNumber !== null) {
            sendNumberToPeer(remotePeerId, localNumber);
        }
    };

    channel.onclose = () => {
        console.log(`Data channel with ${remotePeerId} closed.`);
    };

    channel.onmessage = (event) => {
        console.log(`Message received from ${remotePeerId}:`, event.data);
        try {
            const message = JSON.parse(event.data);
            if (message.type === 'number_update') {
                connectedPeersNumbers.set(remotePeerId, message.number);
                console.log(`Updated number for ${remotePeerId}: ${message.number}`);
                calculateAndDisplaySwarmMaximum();
            }
        } catch (error) {
            console.error("Error parsing message from peer:", error);
        }
    };

    channel.onerror = (error) => {
        console.error(`Data channel error with ${remotePeerId}:`, error);
    };
}

function handleDisconnect(remotePeerId) {
    console.log(`Disconnected from ${remotePeerId}`);
    if (peerConnections[remotePeerId]) {
        peerConnections[remotePeerId].close();
        delete peerConnections[remotePeerId];
    }
    if (dataChannels[remotePeerId]) {
        dataChannels[remotePeerId].close();
        delete dataChannels[remotePeerId];
    }
    removePeerFromUI(remotePeerId);
    connectedPeersNumbers.delete(remotePeerId);
    calculateAndDisplaySwarmMaximum();
    console.log(`Cleaned up resources for ${remotePeerId}.`);
}

// -----------------------------------------------------------------------------
// IRC Client Functions (using irc-framework)
// -----------------------------------------------------------------------------
function initializeIRCClient() {
    if (!ircOptions.localPeerIdForNick) {
        console.error("Cannot connect to IRC: localPeerIdForNick not set in ircOptions.");
        return;
    }
    if (typeof IrcFramework === 'undefined') {
        console.error("IrcFramework is not available. Ensure it's included in the page.");
        const errorDiv = document.createElement('div');
        errorDiv.textContent = "ERROR: IRC Framework library not loaded. Peer discovery via IRC will not work.";
        errorDiv.style.color = "red";
        errorDiv.style.padding = "10px";
        errorDiv.style.backgroundColor = "#fee";
        document.body.insertBefore(errorDiv, document.body.firstChild);
        return;
    }

    ircOptions.nick = ircOptions.localPeerIdForNick;
    console.log(`Initializing IRC client with nick: ${ircOptions.nick} to ${ircOptions.host}:${ircOptions.port}`);

    ircClient = new IrcFramework.Client(ircOptions);
    ircClient.connect();

    ircClient.on('connected', () => {
        console.log('IRC client connected to server.');
    });

    ircClient.on('registered', () => {
        console.log("IRC client registered with the server.");
        if (ircOptions.mainChannel) {
            console.log(`Joining main channel: ${ircOptions.mainChannel}`);
            ircClient.join(ircOptions.mainChannel);
        } else {
            console.warn("Main channel not set in ircOptions, cannot join.");
        }
    });

    ircClient.on('close', () => {
        console.log('IRC client connection closed.');
        if (periodicHelloInterval) clearInterval(periodicHelloInterval);
    });

    ircClient.on('error', (err) => {
        console.error('IRC client error:', err);
        if (err && err.event && err.event.type === 'error' && err.event.target && err.event.target.readyState === WebSocket.CLOSED) {
            console.error("IRC WebSocket connection failed. Check server address, port, and if a WebSocket proxy is needed (e.g. /websocket path).");
        }
    });

    ircClient.on('raw', (event) => {
        if (!event.line.includes("PING") && !event.line.includes("PONG")) {
            console.log("IRC RAW:", event.line);
        }
    });

    ircClient.on('join', (event) => {
        if (!ircClient || !ircClient.user) return; // Guard, ensure ircClient.user is populated
        if (ircClient.user && event.nick.toLowerCase() === ircClient.user.nick.toLowerCase()) {
            console.log(`Successfully joined channel: ${event.channel}`);
            const helloMsg = `HELLO ${localPeerId}`;
            if (ircClient.connected) {
                ircClient.say(ircOptions.mainChannel, helloMsg);
                console.log(`Sent HELLO to ${ircOptions.mainChannel}: ${helloMsg}`);
            }
            if (periodicHelloInterval) clearInterval(periodicHelloInterval);
            periodicHelloInterval = setInterval(() => {
                if (ircClient && ircClient.connected) {
                    const periodicHelloMsg = `HELLO ${localPeerId}`;
                    ircClient.say(ircOptions.mainChannel, periodicHelloMsg);
                    console.log(`Sent periodic HELLO to ${ircOptions.mainChannel}: ${periodicHelloMsg}`);
                } else {
                    if(periodicHelloInterval) clearInterval(periodicHelloInterval);
                }
            }, 3 * 60 * 1000);
        } else {
            console.log(`${event.nick} joined ${event.channel}. Waiting for their HELLO.`);
        }
    });

    ircClient.on('part', (event) => {
        console.log(`${event.nick} left ${event.channel} (${event.message})`);
        if (ircPeers.has(event.nick)) {
            const departingPeerId = ircPeers.get(event.nick).peerId;
            console.log(`Peer ${event.nick} (${departingPeerId}) left. Removing.`);
            ircPeers.delete(event.nick);
            removePeerFromUI(departingPeerId);
            if (peerConnections[departingPeerId]) {
                handleDisconnect(departingPeerId);
            }
        }
    });

    ircClient.on('quit', (event) => {
        console.log(`${event.nick} quit IRC (${event.message})`);
        if (ircPeers.has(event.nick)) {
            const departingPeerId = ircPeers.get(event.nick).peerId;
            console.log(`Peer ${event.nick} (${departingPeerId}) quit. Removing.`);
            ircPeers.delete(event.nick);
            removePeerFromUI(departingPeerId);
            if (peerConnections[departingPeerId]) {
                handleDisconnect(departingPeerId);
            }
        }
    });

    ircClient.on('privmsg', (event) => {
        if (!ircClient || !ircClient.user) return;
        const senderNick = event.nick;
        const target = event.target;
        const message = event.message;

        console.log(`IRC PRIVMSG from ${senderNick} to ${target}: ${message}`);

        if (target.toLowerCase() === ircOptions.mainChannel.toLowerCase()) {
            if (message.startsWith("HELLO ")) {
                const receivedPeerId = message.substring(6).trim();
                if (receivedPeerId === localPeerId) return;

                console.log(`Received HELLO from ${senderNick} with peerId ${receivedPeerId}`);
                if (!ircPeers.has(senderNick) || ircPeers.get(senderNick).peerId !== receivedPeerId) {
                    ircPeers.set(senderNick, { peerId: receivedPeerId, lastHello: Date.now() });
                    console.log(`Added/Updated peer: ${senderNick} -> ${receivedPeerId}`);
                    if (localPeerId < receivedPeerId && (!peerConnections[receivedPeerId] ||
                        (peerConnections[receivedPeerId].connectionState !== 'connected' &&
                         peerConnections[receivedPeerId].connectionState !== 'connecting'))) {
                        console.log(`Discovered new peer ${receivedPeerId} (${senderNick}) via HELLO, initiating connection.`);
                        initiateConnectionToPeer(receivedPeerId, senderNick);
                    }
                } else {
                    ircPeers.get(senderNick).lastHello = Date.now();
                }
            }
        } else if (ircClient.user && target.toLowerCase() === ircClient.user.nick.toLowerCase()) { // Check PM to self
            if (message.startsWith("WEBRTC_SIGNAL:")) {
                try {
                    const signalData = JSON.parse(message.substring(16));
                    const remotePeerId = signalData.senderPeerId;

                    if (!ircPeers.has(senderNick) || ircPeers.get(senderNick).peerId !== remotePeerId) {
                        console.warn(`Received WEBRTC_SIGNAL from ${senderNick} claiming to be ${remotePeerId}, but this doesn't match our records or peer not known via HELLO. Ignoring. Peer data from ircPeers:`, ircPeers.get(senderNick));
                        return;
                    }

                    switch (signalData.type) {
                        case "offer":
                            handleOffer(remotePeerId, senderNick, signalData.data);
                            break;
                        case "answer":
                            handleAnswer(remotePeerId, signalData.data);
                            break;
                        case "candidate":
                            handleCandidate(remotePeerId, signalData.data);
                            break;
                        default:
                            console.warn("Unknown WEBRTC_SIGNAL type:", signalData.type);
                    }
                } catch (e) {
                    console.error("Error parsing WEBRTC_SIGNAL JSON:", e, "Raw message:", message.substring(16));
                }
            }
        }
    });

    ircClient.on('nick in use', (event) => {
        console.warn(`IRC Nick ${event.nick} already in use. Trying ${event.nick + '_'}`);
        ircClient.nick(event.nick + '_');
    });

    ircClient.on('nick', (event) => {
        if (!ircClient || !ircClient.user) return;
        if (event.nick.toLowerCase() === ircClient.user.nick.toLowerCase() && event.new_nick.toLowerCase() !== ircClient.user.nick.toLowerCase()) {
             console.log(`Our nick changed from ${event.nick} to ${event.new_nick}.`);
        }
        if (ircPeers.has(event.nick) && event.nick.toLowerCase() !== ircClient.user.nick.toLowerCase()) {
            const peerData = ircPeers.get(event.nick);
            ircPeers.delete(event.nick);
            ircPeers.set(event.new_nick, peerData);
            console.log(`Peer ${event.nick} changed nick to ${event.new_nick}. Updated ircPeers entry.`);
        }
    });
}

// -----------------------------------------------------------------------------
// WebRTC Signaling Handlers (IRC based)
// -----------------------------------------------------------------------------
function handleOffer(remotePeerId, remoteNick, offerData) {
    console.log(`Received offer from ${remoteNick} (PeerID: ${remotePeerId})`);
    let pc = peerConnections[remotePeerId];
    if (pc && (pc.connectionState === 'connected' || pc.connectionState === 'connecting')) {
        console.log(`Connection to ${remotePeerId} already exists or is connecting. Current state: ${pc.connectionState}. Ignoring new offer for now.`);
        return;
    }
    pc = createPeerConnection(remotePeerId, false); // false: not initiator
    pc.setRemoteDescription(new RTCSessionDescription(offerData))
        .then(() => {
            console.log(`Set remote description for offer from ${remotePeerId}`);
            return pc.createAnswer();
        })
        .then(answer => {
            console.log(`Created answer for ${remotePeerId}`);
            return pc.setLocalDescription(answer);
        })
        .then(() => {
            if (!ircClient || !ircClient.connected) {
                console.error("IRC client not connected, cannot send answer.");
                return;
            }
            const answerSignal = { type: "answer", senderPeerId: localPeerId, data: pc.localDescription };
            ircClient.say(remoteNick, `WEBRTC_SIGNAL:${JSON.stringify(answerSignal)}`);
            console.log(`Sent answer to ${remoteNick} (PeerID: ${remotePeerId})`);
        })
        .catch(error => {
            console.error(`Error processing offer from ${remotePeerId}:`, error);
            handleDisconnect(remotePeerId);
        });
}

function handleAnswer(remotePeerId, answerData) {
    console.log(`Received answer from PeerID: ${remotePeerId}`);
    const pc = peerConnections[remotePeerId];
    if (!pc) {
        console.error(`No peer connection for ${remotePeerId} to handle answer.`);
        return;
    }
    pc.setRemoteDescription(new RTCSessionDescription(answerData))
        .then(() => {
            console.log(`Set remote description for answer from ${remotePeerId}`);
        })
        .catch(error => console.error(`Error processing answer from ${remotePeerId}:`, error));
}

function handleCandidate(remotePeerId, candidateData) {
    console.log(`Received ICE candidate from PeerID: ${remotePeerId}`);
    const pc = peerConnections[remotePeerId];
    if (!pc) {
        console.error(`No peer connection for ${remotePeerId} to handle candidate.`);
        return;
    }
    if (!candidateData) {
        console.log(`Received null/empty ICE candidate from ${remotePeerId}, potentially end of candidates.`);
        return;
    }
    pc.addIceCandidate(new RTCIceCandidate(candidateData))
        .then(() => {
            console.log(`Added ICE candidate from ${remotePeerId}`);
        })
        .catch(error => console.error(`Error adding ICE candidate for ${remotePeerId}:`, error.toString(), "Candidate:", candidateData));
}

// -----------------------------------------------------------------------------
// Signaling Logic (IRC based - main initiator function)
// -----------------------------------------------------------------------------
function initiateConnectionToPeer(remotePeerId, remoteNick) {
    if (!ircClient || !ircClient.connected) {
        console.error("IRC client not connected. Cannot initiate connection to", remoteNick);
        return;
    }
    if (peerConnections[remotePeerId] &&
        (peerConnections[remotePeerId].connectionState === 'connected' ||
         peerConnections[remotePeerId].connectionState === 'connecting')) {
        console.log(`Already connected or connecting to ${remotePeerId} (${remoteNick}). Skipping initiation.`);
        return;
    }
    console.log(`Initiating WebRTC connection to ${remoteNick} (PeerID: ${remotePeerId})`);
    const pc = createPeerConnection(remotePeerId, true); // true for initiator

    pc.createOffer()
        .then(offer => {
            console.log(`Created offer for ${remotePeerId}`);
            return pc.setLocalDescription(offer);
        })
        .then(() => {
            if (!ircClient || !ircClient.connected) {
                 console.error("IRC client disconnected before offer could be sent to", remoteNick);
                 throw new Error("IRC client not connected");
            }
            const offerSignal = { type: "offer", senderPeerId: localPeerId, data: pc.localDescription };
            ircClient.say(remoteNick, `WEBRTC_SIGNAL:${JSON.stringify(offerSignal)}`);
            console.log(`Sent offer to ${remoteNick} (PeerID: ${remotePeerId})`);
        })
        .catch(error => {
            console.error(`Error initiating connection to ${remotePeerId} (${remoteNick}):`, error);
            handleDisconnect(remotePeerId);
        });
}

// -----------------------------------------------------------------------------
// Application Logic (Number Generation & Swarm Calculation)
// -----------------------------------------------------------------------------
function generateAndBroadcastNumber() {
    localNumber = Math.floor(Math.random() * 1000) + 1;
    console.log(`Generated new local number: ${localNumber}`);
    localNumberDisplay.textContent = localNumber;

    const message = JSON.stringify({ type: 'number_update', peerId: localPeerId, number: localNumber });
    for (const peerId in dataChannels) {
        if (dataChannels[peerId].readyState === 'open') {
            console.log(`Sending number ${localNumber} to ${peerId}`);
            dataChannels[peerId].send(message);
        } else {
            console.warn(`Data channel with ${peerId} is not open. State: ${dataChannels[peerId].readyState}`);
        }
    }
    calculateAndDisplaySwarmMaximum();
}

function sendNumberToPeer(remotePeerId, number) {
    if (dataChannels[remotePeerId] && dataChannels[remotePeerId].readyState === 'open') {
        const message = JSON.stringify({ type: 'number_update', peerId: localPeerId, number: number });
        console.log(`Sending number ${number} to ${remotePeerId}`);
        dataChannels[remotePeerId].send(message);
    } else {
        console.warn(`Cannot send number to ${remotePeerId}, data channel not open or doesn't exist.`);
    }
}

function calculateAndDisplaySwarmMaximum() {
    let max = localNumber !== null ? localNumber : -Infinity;
    connectedPeersNumbers.forEach((number, peerId) => {
        if (number > max) {
            max = number;
        }
    });
    swarmMaximum = max === -Infinity ? null : max;
    swarmMaxDisplay.textContent = swarmMaximum !== null ? swarmMaximum : "N/A";
    console.log(`Swarm maximum calculated: ${swarmMaximum}`);
}

// -----------------------------------------------------------------------------
// Initialization
// -----------------------------------------------------------------------------
function initializeApp() {
    console.log("App Initializing...");

    localPeerId = generatePeerId();
    localPeerIdDisplay.textContent = localPeerId;
    console.log(`Local Peer ID: ${localPeerId}`);

    let safeNick = localPeerId.replace(/[^a-zA-Z0-9_-\[\]\{\}\^`|]/g, '');
    if (!safeNick) {
        safeNick = "swarmpeer" + Math.floor(Math.random() * 1000);
    }
    if (safeNick.length > 16) {
        safeNick = safeNick.substring(0, 16);
    }
    ircOptions.localPeerIdForNick = `peer_${safeNick}`;
    ircOptions.mainChannel = "#poc-swarm-discovery";
    console.log("Generated IRC Nick for framework:", ircOptions.localPeerIdForNick);

    localNumberDisplay.textContent = "Click 'Generate' to start";
    swarmMaxDisplay.textContent = "Waiting for numbers...";

    if (generateNumberBtn) {
        generateNumberBtn.addEventListener('click', generateAndBroadcastNumber);
    } else {
        console.error("Generate New Number button not found.");
    }

    // Initialize IRC Client (handles discovery and WebRTC signaling)
    initializeIRCClient();

    // Note: All Firebase-related signaling and presence announcement logic has been removed.
    // IRC is now the sole mechanism for discovery and signaling.

    // Peer timeout check
    if (peerTimeoutInterval) clearInterval(peerTimeoutInterval);
    peerTimeoutInterval = setInterval(() => {
        const now = Date.now();
        const timeout = 7 * 60 * 1000; // 7 minutes
        for (const [nick, data] of ircPeers.entries()) {
            if (now - data.lastHello > timeout) {
                console.log(`Peer ${nick} (${data.peerId}) timed out (no HELLO for ${timeout/60000} mins). Removing.`);
                ircPeers.delete(nick);
                removePeerFromUI(data.peerId);
                if (peerConnections[data.peerId]) {
                    handleDisconnect(data.peerId);
                }
            }
        }
    }, 1 * 60 * 1000); // Check every minute

    generateAndBroadcastNumber();
}

document.addEventListener('DOMContentLoaded', initializeApp);

window.addEventListener('beforeunload', () => {
    console.log("Cleaning up before unload...");

    if (periodicHelloInterval) clearInterval(periodicHelloInterval);
    if (peerTimeoutInterval) clearInterval(peerTimeoutInterval);

    if (ircClient && ircClient.connected) {
        console.log("Quitting IRC client.");
        ircClient.quit("Leaving - P2P Swarm Node");
    } else if (ircClient) {
        console.log("IRC client exists but not connected, attempting to disconnect.");
        ircClient.disconnect();
    }

    if (localPeerId) {
        // Firebase cleanup has been removed.

        for (const peerId in peerConnections) {
            handleDisconnect(peerId);
        }
    }
});

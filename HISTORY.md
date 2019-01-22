# Release History

### 1.0.2 (2019-01-22)

* **Feature** - Change nonce handling for less lock time and faster throughput
* **Fix** - Notify on bounty post failure due to low balance
* **Feature** - Pass mask, verdicts, metadata to bid
* **Fix** - Remove block event logs
* **Fix** - Recover from unhandled exception
* **Fix** - Fix eicar ambassador bad method name

### 1.0.1 (2019-01-03)

* **Fix** - Client should exit with `os._exit` when running under Windows
* **Fix** - Make default handler methods private
* **Feature** - Submit bounties via a queue with backpressure
* **Fix** - Remove default backend of 'scratch'

### 1.0 (2019-01-01)

No change from rc6. Releasing 1.0.

### 1.0rc6 (2018-12-31)

* **Fix** - catch timeouts during requests to polyswarmd

### 1.0rc5 (2018-12-28)

* **Feature** - add clamav as an example arbiter
* **Fix** - create asyncio locks after we change the event loop
* **Fix** - attempt reconnect on connection errors
* **Fix** - do not trust polyswarmd

### 1.0rc4 (2018-12-24)

* **Fix** - check transaction responses
* **Fix** - return empty dict instead of None on transaction error
* **Fix** - better handling of polyswarmd responses
* **Fix** - don't clobber API key if one is set
* **Fix** - revise clamav example microengine to use async socket
* **Fix** - asyncio loop change detection for windows hosts

### 1.0rc3 (2018-12-15)

* **Fix** - function name corrections that were missed in rc2
* **Fix** - remove awaits added in rc2 that don't belong

### 1.0rc2 (2018-12-14)

* **Fix** - duplicate bounty event handing
* **Fix** - enhance log messages with more useful content
* **Feature** - allow overriding API key per request
* **Fix** - code cleanup and formatting; enhance events class to include block_number and txhash as function args

### 1.0rc1 (2018-12-11)

* **Fix** - corrected minimum python3 version

### 1.0rc0 (2018-12-07)

Leading up to our PolySwarm 1.0 release, we reset the numbering to 1.0 with release candidates.

* **Feature** - This is the first release published to PyPi.

### 0.2.0 (2018-11-28)

* **Feature**: Converted ambassador, arbiter, microengine, and scanner classes to be abstract classes. Updated sample engines to use new design patterns.

The update from 0.1.2 to 0.2.0 is a breaking change for Ambassadors, Arbiters, and Microengines.

#### polyswarmclient <= 0.1.2 used this pattern:

**Ambassadors**
```
from polyswarmclient.ambassador import Ambassador
class CustomAmbassador(Ambassador):
    # Ambassador implementation here
```

**Arbiters**
```
from polyswarmclient.arbiter import Arbiter
class CustomArbiter(Arbiter):
    # Arbiter implementation here
```

**Microengines**
```
from polyswarmclient.microengine import Microengine
class CustomMicroengine(Microengine):
    # Microengine implementation here
```

#### polyswarmclient >= 0.2.0, instead use the following pattern:

**Ambassadors**
```
from polyswarmclient.abstractambassador import AbstractAmbassador
class Ambassador(AbstractAmbassador):
    # Ambassador implementation here
```

**Arbiters**
```
from polyswarmclient.abstractarbiter import AbstractArbiter
class Arbiter(AbstractArbiter):
    # Arbiter implementation here
```

**Microengines**
```
from polyswarmclient.abstractmicroengine import AbstractMicroengine

class Microengine(AbstractMicroengine):
    # Microengine implementation here
```

This implies that custom microengines now only need to provide their python module name to the `--backend` argument
instead of `module_name:CustomMicroengine`.

Additionally, as of `polyswarmclient >= 0.2.0`:

* `AbstractArbiter.scan()` and `AbstractMicroengine.scan()` will now raise an exception if it
has not been overridden by a sub-class and the subclass did not provide a scanner to the constructor.
* `AbstractAmbassador.next_bounty()` will now raise an exception if not overridden by sub-class.


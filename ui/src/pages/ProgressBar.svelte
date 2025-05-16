<script lang="ts">
	import {onDestroy, onMount} from 'svelte';

  	export let alertStatusID;
	export let alertID;

	let dbElapsedSla;
	let currstate;

	onMount(async () => {
		console.log("I JUST MOUNTED AGAIN MOTHERFUCKER");
        dbElapsedSla = await fetchAlertSla();
        console.log("DB_Data: ", dbElapsedSla);

		currstate = MyState.RUNNING;

      	start();

	   cleanupEffect = () => clearInterval(interval);
	});

  	const MyState ={
		NEW: 0,
	  	RUNNING: 1,
	    PAUSED: 2,
  	};


  	//let { startDateTime = "01/02/2025 14:30", endDateTime = "01/02/2025 14:31" } = $props();
  	export let startDateTime = "01/02/2025 14:30";
  	export let endDateTime = "01/02/2025 14:30";
  	let timecomputed = calculateDuration(); //calculate duration betwwen two timestamps in seconds
  	$: elapsed = 0;
  	$: duration = timecomputed;
  	let interval: number
  	let oldElapsedTime = 0;
  	let currTimeEpoch = 0;
  	let startTimeEpoch = getSecondsSinceEpoch(startDateTime);
  	$: SLAbreached = false;

	function start() {
	  interval = setInterval(() => {
		  if(currstate === MyState.RUNNING) {
			  //calculate curr time
			  currTimeEpoch = Math.floor((Date.now()) / (1000 * 60)) * 60;
			  if(dbElapsedSla < 0){ //SLA not yet completed
				  elapsed = currTimeEpoch - startTimeEpoch + oldElapsedTime;
				  console.log("elapsed: "+elapsed);
			  }
			  else { //SLA is not -1 therefore was completed sometime before
				  elapsed = dbElapsedSla;
				  clearInterval(interval)
				  currstate = MyState.PAUSED;
			  }

			  if (elapsed > duration) {
				  elapsed = duration
				  clearInterval(interval)
				  SLAbreached = true;
			  }
			  if (alertStatusID === 4){
		  		complete();
			  }
		  }
	  }, 1000)
    }

	function getSecondsSinceEpoch(dateString) {
		// Split the input string into date and time parts
		const [datePart, timePart] = dateString.split(' ');
		// Split the date part into day, month, and year
		const [day, month, year] = datePart.split('/');
		// Split the time part into hours and minutes
		const [hours, minutes] = timePart.split(':');
		// Create a Date object (note: months are 0-based in JavaScript)
		const date = new Date(year, month - 1, day, hours, minutes);
		// Get the number of seconds since the Unix epoch
		const secondsSinceEpoch = Math.floor(date.getTime() / 1000);
		return secondsSinceEpoch;
	}


  	//this should actually fetch for column "alert_elapsed_sla"
  	// it will either have -1 or other int value for SLA completed seconds
  	async function fetchAlertSla() {
        try {
            const response = await fetch(`alerts/api/get_elapsed_sla_api/${alertID}`);
            const data = await response.json();

            // Declare the variable properly
            const elapsedSla = data.data.alert_elapsed_sla;

            return elapsedSla;
        }
        catch (error) {
            console.error('Error fetching data:', error);
            throw error;
        }
    }

	async function writeSlaData() {
        try {
            const response = await fetch(`alerts/api/set_elapsed_sla_api/${alertID}/${elapsed}`);

            const result = await response.json();
        	console.log('Update result:', result);
        }
        catch (error) {
            console.error('Error fetching data:', error);
            throw error;
        }
    }


  	function complete() {
	  	clearInterval(interval)
	  	currstate = MyState.PAUSED;
	  	if (elapsed < 0){
		  	elapsed = 0;
	  	}
	  	console.log("elapsedFromComplete "+elapsed);
	  	writeSlaData();
  	}

	function pause() {
		currstate = MyState.PAUSED;
		console.log("Paused!");
		oldElapsedTime = elapsed;
	}

	function resume() {
		currstate = MyState.RUNNING;
		startTimeEpoch = (Math.floor((Date.now()) / (1000 * 60)) * 60);
		console.log("Runing!");
	}

	let cleanupEffect;

	onDestroy(() => {
		if (cleanupEffect) cleanupEffect();
	});

	function calculateDuration() {
		try {
			// Extract date and time components
			let [date1, time1] = startDateTime.split(" ");
			let [date2, time2] = endDateTime.split(" ");
			let [d1, m1, y1] = date1.split("/").map(Number);
			let [d2, m2, y2] = date2.split("/").map(Number);
			let [h1, min1] = time1 ? time1.split(":").map(Number) : [0, 0];
			let [h2, min2] = time2 ? time2.split(":").map(Number) : [0, 0];
			// Convert to JS Date objects (JS months are 0-based)
			let start = new Date(y1, m1 - 1, d1, h1, min1);
			let end = new Date(y2, m2 - 1, d2, h2, min2);
			let totalTime = 0;
			// Calculate the difference in milliseconds
			let diffMs = end - start;
			if (diffMs < 0) {
				totalTime = 0;
				return;
			}
			// Convert milliseconds to days, hours, minutes, and seconds
			let totalSeconds = Math.floor(diffMs / 1000);
			//let days = Math.floor(totalSeconds / 86400);
			//let hours = Math.floor((totalSeconds % 86400) / 3600);
			//let minutes = Math.floor((totalSeconds % 3600) / 60);
			//let seconds = totalSeconds % 60;
			totalTime = totalSeconds;
			return totalTime;
		} catch (error) {
			console.error("Invalid date format:", error);
		}
	}
    console.log(calculateDuration());
</script>

<div class="grid-gap">
	<div class="progress-container col-md-12" style="display: flex;justify-content: center;">
		<div class="col-md-12" style="padding-top: 5px;">
			<div class="row col-md-12" style="display: flex;justify-content: center;">
      			<p>{startDateTime} - {endDateTime}</p>
			</div>

			<div class="row col-md-12" style="display: flex;justify-content: center; padding-bottom: 5px;">
				<span>Elapsed time:</span>
			</div>

			<label class="row col-md-12" style="display: flex;justify-content: center;">
				<progress class:completed={currstate === MyState.PAUSED} class:breached={SLAbreached} max={duration} value={elapsed}></progress>
			</label>

			<div class="row col-md-12" style="display: flex;justify-content: center;">
				<p>{elapsed.toFixed(1)}s</p>
			</div>
		</div>
	</div>

    {#if duration === elapsed}
        <p class="row col-md-12" style="display: flex;justify-content: center;"><strong>SLA breached!</strong></p>
	{/if}
</div>


<style>
	.progress-container {
    width: 100%;
    padding: 5px;
    border: 2px solid grey;
    border-radius: 10px;
    background-color: #f3f3f3;
  }

  progress {
    width: 90%;
    height: 10px;
    -webkit-appearance: none;
    appearance: none;
  }

  p {
	   height: 10px;
  }

  progress::-webkit-progress-bar {
    background-color: #ffffff;
    border-radius: 10px;
  }

  progress::-webkit-progress-value {
    background-color: #00b5f1;
    border-radius: 10px;
  }

  /* When complete, change the progress bar's value color */
  .completed::-webkit-progress-value {
    background-color: green;
  }

  .breached::-webkit-progress-value {
    background-color: red;
  }

  progress::-moz-progress-bar {
    background-color: lightblue;
    border-radius: 10px;
  }
</style>
<script lang="ts">
    import ProgressBar from "./ProgressBar.svelte";


	//setting up startDateTime value
	let startDateTime = "01/02/2025 14:30";//defalut value
    let UTCstartDateTime = "01/02/2025 14:30";//defalut value
    export let IRIStime;

    const date = new Date(IRIStime);
    const UTCdate = new Date(IRIStime);

    date.setHours(date.getHours() + 2); //date.getHours() + current Timezone offset
    UTCdate.setHours(UTCdate.getHours());

    // Get day, month, year, hours, and minutes with proper padding
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0'); // Months are 0-based
    const year = date.getFullYear();
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');


    // Get day, month, year, hours, and minutes with proper padding
    const UTCday = String(UTCdate.getDate()).padStart(2, '0');
    const UTCmonth = String(UTCdate.getMonth() + 1).padStart(2, '0'); // Months are 0-based
    const UTCyear = UTCdate.getFullYear();
    const UTChours = String(UTCdate.getHours()).padStart(2, '0');
    const UTCminutes = String(UTCdate.getMinutes()).padStart(2, '0');

    startDateTime = `${day}/${month}/${year} ${hours}:${minutes}`;



    UTCstartDateTime = `${UTCday}/${UTCmonth}/${UTCyear} ${UTChours}:${UTCminutes}`;


    export let alertStatusID;
    export let alertSevID;
    export let SLA;
    export let alertCustomerID;
    export let alertID;


    console.log(`MUJ START DATE TIME JE ${startDateTime}\nMUJ SLA IG TYVOLE ${SLA} MUJ ALERT ID ${alertID}`);
    console.log(`MUJ UTC START DATE TIME JE ${UTCstartDateTime}\nMUJ SLA IG TYVOLE`);


    let workingDays = [];
	let startHour = 8;
    let endHour = 20;

    //parsing SLA string
    const clients = JSON.parse(SLA);
    const myClient = clients.find(client => client.client_id === alertCustomerID)?.sla;

    // Split the SLA into components
    if (myClient.includes(':')) {
  		const [days, startTime, endTime] = myClient.split(':');

  		// Process working days
  		workingDays = days.split(', ').map(day => day.trim());

  		// Convert times to numbers
  		startHour = parseInt(startTime, 10);
  		endHour = parseInt(endTime, 10);
	} else {
  		// Handle case with no times (just days)
  		workingDays = myClient.split(', ').map(day => day.trim());
	}

    const workingHours = {
    	start: startHour, // 8:00 AM
    	end: endHour // 8:00 PM
  	};

	//setting up severity
	const SEVERITY ={
		LOW: 12,
	  	INFORMATIONAL: 24,
		MEDIUM: 6,
		HIGH: 1
  	};

	//setting up endDateTime value
	let endDateTime = "01/02/2025 22:31"; //default value
	endDateTime = calculateEndDateTime(startDateTime, alertSevID);
    let UTCendDateTime = calculateEndDateTime(UTCstartDateTime, alertSevID);
	console.log("EndTimeeeee:"+endDateTime);
    console.log("EndTIME UTC VOLE:"+UTCendDateTime);

	//const workingDays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday'];

	let result;
    let resultUTC;
	result = getClosestWorkingTime(startDateTime);
    resultUTC = getClosestWorkingTime(UTCstartDateTime);
	console.log("startDateTime: "+startDateTime);
    console.log("UTCstartDateTime: "+UTCstartDateTime);
	result = formatDateTime(result);
    result = formatDateTime(resultUTC);
	console.log("result: "+result);
    console.log("resultUTC: "+resultUTC);
	let computedValue;
    let computedValueUTC;
	if(result !== true  ){
		computedValue = calculateEndDateTime(result, alertSevID);
		console.log("computed value: "+computedValue);
	}
    if(resultUTC !== true){
        computedValueUTC = calculateEndDateTime(resultUTC, alertSevID);
        console.log("computed value: "+computedValueUTC)
    }

	//input in formated timestamp
    //returns formated timestamp
    function calculateEndDateTime(startDateTime, severity) {
  		let secondsEpoch = getSecondsSinceEpoch(startDateTime);
  		// Add the appropriate time in seconds based on severity
        //1 - Medium
        //2 - Unspecified
        //3 - Informational
        //4 - Low
        //5 - High
        //6 - Critical
  		if (severity === 4) { //Low
    		secondsEpoch += SEVERITY.LOW * 3600;
  		}
		else if (severity === 3) {
    		secondsEpoch += 24 * 3600;
  		}
		else if (severity === 1) { //medium
    		secondsEpoch += SEVERITY.MEDIUM * 3600;
  		}
		else if (severity === 5) {
    		secondsEpoch = secondsEpoch+600;
  		}
        else {
            secondsEpoch += 12 * 3600;
        }
  		// Return the formatted date-time string
  		return getFormattedDateFromTimestamp(secondsEpoch);
	}

    //inputs formated timestamp
    //returns num of seconds
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

	//input num of seconds
    //returns formated timestamp
    function getFormattedDateFromTimestamp(timestamp) {
        // Create a Date object from the timestamp (multiply by 1000 to convert seconds to milliseconds)
        const date = new Date(timestamp * 1000);
        // Extract day, month, year, hours, and minutes
        const day = String(date.getDate()).padStart(2, '0'); // Ensure 2 digits
        const month = String(date.getMonth() + 1).padStart(2, '0'); // Months are 0-based
        const year = date.getFullYear();
        const hours = String(date.getHours()).padStart(2, '0'); // Ensure 2 digits
        const minutes = String(date.getMinutes()).padStart(2, '0'); // Ensure 2 digits
        // Format the date and time as DD/MM/YYYY HH:MM
        const formattedDate = `${day}/${month}/${year} ${hours}:${minutes}`;
        return formattedDate;
    }

    //converts the formated timestamp to Date object - easier to work with
	function parseDateTime(dateTime) {
    	const [date, time] = dateTime.split(' ');
    	const [day, month, year] = date.split('/').map(Number);
    	const [hours, minutes] = time.split(':').map(Number);
   	    return new Date(year, month - 1, day, hours, minutes);
    }

    //inputs Date object and
    // returns formated timestamp string
    //if not Date object inputted return true - indicates we are in current working hours
    function formatDateTime(date) {
		if (!(date instanceof Date)) {
      		return true;
    	}
    	const day = String(date.getDate()).padStart(2, '0');
    	const month = String(date.getMonth() + 1).padStart(2, '0'); // Months are zero-based
    	const year = date.getFullYear();
   	 	const hours = String(date.getHours()).padStart(2, '0');
    	const minutes = String(date.getMinutes()).padStart(2, '0');
    	return `${day}/${month}/${year} ${hours}:${minutes}`;
  	}

    // Check if it's a working day and within working hours - if yes return true else return next working time
    //generated by deepSeek (R1) on 7th of March 2025 base on input:
    // "generate a JS function that will take input date in form
    // DD/MM/YYYY HH:MM and return true for input is current working time
    // else return nextWorkingTime based on array WorkingDays and int StartHour
    // and int EndHour"
    function getClosestWorkingTime(inputDateTime) {
    	const inputDate = parseDateTime(inputDateTime);
    	const currentDayIndex = inputDate.getDay(); // 0 for Sunday, 1 for Monday, etc.
   	 	const currentHour = inputDate.getHours();
    	// Convert day index to a string name
    	const dayName = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
    	// Check if it's a working day and within working hours
    	if (
      	workingDays.includes(dayName[currentDayIndex]) &&
      	currentHour >= workingHours.start &&
      	currentHour < workingHours.end
    	) {
      		return true;
    	}
    	// Calculate the closest working time
    	const closestTime = new Date(inputDate);
    	// If it's outside working hours but on a working day
    	if (workingDays.includes(dayName[currentDayIndex])) {
      		if (currentHour < workingHours.start) {
        		closestTime.setHours(workingHours.start, 0, 0, 0);
        		return closestTime;
      		}
      		if (currentHour >= workingHours.end) {
        		let daysToAdd = 1;
            	while (!workingDays.includes(dayName[(currentDayIndex + daysToAdd) % 7])) {
          			daysToAdd++;
        		}
        		closestTime.setDate(closestTime.getDate() + daysToAdd);
      		}
    	}
        else {
      		// If it's not a working day, find the next working day
      		let daysToAdd = 1;
      		while (!workingDays.includes(dayName[(currentDayIndex + daysToAdd) % 7])) {
        		daysToAdd++;
      		}
      		closestTime.setDate(closestTime.getDate() + daysToAdd);
    	}
    	// Set the time to the start of working hours
    	closestTime.setHours(workingHours.start, 0, 0, 0);
    	return closestTime;
  	}
</script>

<div class="grid-gap">
  {#if result === true} <!-- if within working hours -->
	  <ProgressBar startDateTime={startDateTime} {endDateTime} {alertStatusID} {alertID}/>
  {:else} <!-- if not within working hours - recompute endDateTime-->
	  <ProgressBar startDateTime={result} endDateTime={computedValue} {alertStatusID} {alertID}/>
  {/if}
</div>
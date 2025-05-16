<script>
	import SLAbar from "./SLAbar.svelte";
    let isVisible = true;
	export let IRIStime;
	export let alertStatusID;
	export let alertSevID;
	export let alertCustomerID;
	export let SLA;
	export let alertID;


</script>

<div class="grid-gap">
		<div style:display={isVisible ? 'block' : 'none'}>
			<SLAbar {IRIStime} {alertStatusID} {alertSevID} {SLA} {alertCustomerID} {alertID}/>
		</div>
</div>
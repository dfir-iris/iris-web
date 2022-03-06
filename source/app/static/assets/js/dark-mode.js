"use strict";

// Setting Color

$(window).resize(function() {
	$(window).width();
});



$('body').attr('data-background-full', 'dark');
$('.logo-header').attr('data-background-color', 'dark2');
$('.sidebar').attr('data-background-color', 'dark2');
$('body').attr('data-background-color', 'dark');
$('.main-header .navbar-header').attr('data-background-color', 'dark2');
$('.navbar-header').removeClass('bg-primary-gradient');
$('.nav-bottom').removeClass('bg-primary').addClass('bg-dark2');
$('.panel-header').removeClass('bg-info-gradient').addClass('bg-dark-gradient');
$('.navbar .navbar-header').attr('data-background-color', 'dark2');
$('table').removeClass('table-bordered');

layoutsColors();



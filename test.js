function run_test()
{
	var regarray = [{'phone':'+1234567890,+1987654320', 'mail':'mail@example.com', 'name':'ryuu', 'pass':'ryuu3', 'default_currency':'USD'}, {'phone':'+917587224191', 'mail':'alka.nverma@gmail.com', 'name':'mom', 'pass':'mom3', 'default_currency':'INR'}, {'phone':'+919406103675', 'mail':'acverma@outlook.com', 'name':'dad', 'pass':'dad3', 'default_currency':'INR'}, {'phone':'+1122334455', 'mail':'mail2@example.com', 'name':'ginnie', 'pass':'ginnie3', 'default_currency':'USD'}];
	regarray.forEach(function(element)
	{
		$.ajax
		(
			{
				url: "http://127.0.0.1:5000/register/",
				type: 'post',
    			dataType: 'json',
				data: element,
				success: function(result)
				{
					$("#div1").html(JSON.stringify(result));
					$('#div1').html($('#div1').html().replace(/\\n/g, '<br />'));
					console.log(result);
				}
			}
		);
	}, this);
}
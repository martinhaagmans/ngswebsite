function fancyTables() {
    const tables = document.getElementsByTagName("table");

    for (let i = 0; i < tables.length; i++) {
        let table_id = tables[i].getAttribute("id")
        let table = $("#" + table_id).DataTable({
            dom: '<Bf<t>lip>',
            paging: false,
            searching: false,
            info: false,
            ordering: false,
            buttons: ['copy', 'csv', 'excel', 'print']
            });

    }
}

function fetchJSON(url, callback) {
    let httpRequest = new XMLHttpRequest();
    httpRequest.onreadystatechange = function() {
        if (httpRequest.readyState === 4) {
            if (httpRequest.status === 200) {
                let data = JSON.parse(httpRequest.responseText);
                if (callback) callback(data);
            }
        }
    };
    httpRequest.open('GET', url);
    httpRequest.send(); 
}

function getData(url){
    const combinedArray = [], labelArray = [], dataArray = [] ;
        fetchJSON(url, function(data){
            for (let arr of data.data){
                labelArray.push(arr['genesis']);           
                dataArray.push(arr['count']);           
            }
        });

    combinedArray.push(labelArray,  dataArray)
    return combinedArray ;
}   


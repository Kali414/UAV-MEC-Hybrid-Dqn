// document.addEventListener("DOMContentLoaded", () => {

//     const form = document.getElementById("simulationForm");
//     const resultsSection = document.getElementById("simulationResults");

//     let latencyBarChart, energyBarChart, qoeBarChart, breakdownChart;

//     form.addEventListener("submit", async (e) => {
//         e.preventDefault();

//         const btn = form.querySelector("button[type='submit']");
//         btn.disabled = true;
//         btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Running...`;

//         // FIX: Properly extract form values with correct field names
//         const payload = {
//             uavCount: Number(document.getElementById("uavCount").value),
//             userCount: Number(document.getElementById("userCount").value),
//             bandwidth: Number(document.getElementById("bandwidth").value),
//             taskSize: Number(document.getElementById("taskSize").value),
//             cycles: Number(document.getElementById("cycles").value),
//             areaSize: Number(document.getElementById("areaSize").value),
//             uavRange: Number(document.getElementById("uavRange").value),
//             simSteps: Number(document.getElementById("simSteps").value),
//             userCPU: Number(document.getElementById("userCPU").value),
//             uavCPU: Number(document.getElementById("uavCPU").value),
//             cloudCPU: Number(document.getElementById("cloudCPU").value),
//             kappaMU: Number(document.getElementById("kappaMU").value),
//             kappaUAV: Number(document.getElementById("kappaUAV").value),
//             uavBattery: Number(document.getElementById("uavBattery").value)
//         };

//         console.log("Sending payload:", payload); // Debug log
        
//         try {
//             const response = await fetch("/result", {
//                 method: "POST",
//                 headers: { "Content-Type": "application/json" },
//                 body: JSON.stringify(payload)
//             });

//             if (!response.ok) {
//                 const errorText = await response.text();
//                 throw new Error(`Server error: ${response.status} - ${errorText}`);
//             }

//             const result = await response.json();
//             console.log("Received result:", result); // Debug log
            
//             updateResults(result);
//             drawEnvironment(result);
//             resultsSection.style.display = "block";

//         } catch (err) {
//             alert(`❌ Simulation Failed: ${err.message}`);
//             console.error("Error details:", err);
//         }

//         btn.disabled = false;
//         btn.innerHTML = "▶ Run Simulation";
//     });


//     const avg = arr => arr.reduce((a,b)=>a+b,0) / arr.length;


//     function updateResults(data){
//         document.getElementById("successRate").textContent = `${(avg(data.Hybrid.QoE) * 100).toFixed(1)}%`;
//         document.getElementById("avgLatency").textContent = `${avg(data.Hybrid.Latency).toFixed(2)}ms`;
//         document.getElementById("energyUsage").textContent = `${avg(data.Hybrid.Energy).toFixed(2)} J`;
//         document.getElementById("qoeScore").textContent = avg(data.Hybrid.QoE).toFixed(2);

//         drawCharts(data);
//     }


//     function drawCharts(data){

//         [latencyBarChart, energyBarChart, qoeBarChart, breakdownChart]?.forEach(c=>c?.destroy());

//         latencyBarChart = new Chart(document.getElementById("latencyChart"), {
//             type:"bar",
//             data:{
//                 labels:["DQN","AGSP","Hybrid"],
//                 datasets:[{
//                     label:"Latency (ms)",
//                     data:[
//                         avg(data.DQN.Latency),
//                         avg(data.AGSP.Latency),
//                         avg(data.Hybrid.Latency)
//                     ],
//                     backgroundColor:["#4361ee","#f59e0b","#10b981"]
//                 }]
//             },
//             options:{responsive:true}
//         });

//         energyBarChart = new Chart(document.getElementById("energyChart"), {
//             type:"bar",
//             data:{
//                 labels:["DQN","AGSP","Hybrid"],
//                 datasets:[{
//                     label:"Energy (J)",
//                     data:[avg(data.DQN.Energy), avg(data.AGSP.Energy), avg(data.Hybrid.Energy)],
//                     backgroundColor:["#ef4444","#f59e0b","#10b981"]
//                 }]
//             },
//             options:{responsive:true}
//         });

//         qoeBarChart = new Chart(document.getElementById("qoeChart"), {
//             type:"bar",
//             data:{
//                 labels:["DQN","AGSP","Hybrid"],
//                 datasets:[{
//                     label:"QoE",
//                     data:[avg(data.DQN.QoE), avg(data.AGSP.QoE), avg(data.Hybrid.QoE)],
//                     backgroundColor:["#4361ee","#f59e0b","#10b981"]
//                 }]
//             },
//             options:{responsive:true}
//         });
//     }


//     function drawEnvironment(data) {
//     const canvas = document.getElementById("uavEnvironment");
//     canvas.innerHTML = "";

//     if (!data.positions) {
//         canvas.innerHTML = "<p style='padding:20px;text-align:center;'>No visualization data</p>";
//         return;
//     }

//     const bestAlgo = ["DQN", "AGSP", "Hybrid"].sort(
//         (a, b) => avg(data[b].QoE) - avg(data[a].QoE)
//     )[0];

//     const pos = data.positions;
//     const actions = data[bestAlgo]?.Offloading;

//     if (!actions || actions.length === 0) {
//         canvas.innerHTML = "<p style='padding:20px;text-align:center;'>No offloading pattern to visualize</p>";
//         return;
//     }

//     const bestAction = actions.at(-1);
//     const uavColors = ["#6a0dad", "#1e40af", "#047857", "#fb923c", "#8b5cf6"];
//     const radius = Number(document.getElementById("uavRange").value);

//     // Draw UAV coverage zones first so nodes render above
//     pos.uavs?.forEach((u, idx) => {
//         const range = document.createElement("div");
//         range.className = "uavRangeCircle";
//         range.style.width = radius * 2 + "px";
//         range.style.height = radius * 2 + "px";
//         range.style.left = (u[0] - radius) + "px";
//         range.style.top = (u[1] - radius) + "px";
//         range.style.borderColor = uavColors[idx % uavColors.length];
//         canvas.appendChild(range);
//     });

//     // Draw Users + connections
//     pos.users.forEach((user, i) => {
//         const dot = document.createElement("div");
//         dot.className = "userNode";
//         dot.style.left = user[0] + "px";
//         dot.style.top = user[1] + "px";
//         canvas.appendChild(dot);

//         const a = bestAction[i];

//         if (a === 0) {
//             dot.style.background = "gray"; // Local computation
//         } 
//         else if (a > 0 && a <= pos.uavs.length) {
//             const color = uavColors[(a - 1) % uavColors.length];
//             dot.style.background = color;
//             drawLine(canvas, user, pos.uavs[a - 1], color);
//         } 
//         else {
//             dot.style.background = "red"; // Cloud offload
//             drawLine(canvas, user, pos.cloud, "red");
//         }
//     });

//     // Draw UAVs + label
//     pos.uavs.forEach((u, idx) => {
//         const dot = document.createElement("div");
//         dot.className = "uavNode";
//         dot.style.left = u[0] + "px";
//         dot.style.top = u[1] + "px";
//         dot.style.background = uavColors[idx % uavColors.length];

//         const label = document.createElement("span");
//         label.className = "label";
//         label.innerText = `UAV${idx + 1}`;
//         label.style.left = (u[0] + 15) + "px";
//         label.style.top = (u[1] - 5) + "px";

//         canvas.appendChild(dot);
//         canvas.appendChild(label);
//     });

//     // Draw Cloud + Label
//     if (pos.cloud) {
//         const cloud = document.createElement("div");
//         cloud.className = "uavNode";
//         cloud.style.background = "red";
//         cloud.style.left = pos.cloud[0] + "px";
//         cloud.style.top = pos.cloud[1] + "px";
//         cloud.style.borderRadius = "0px";
//         cloud.style.width = "16px";
//         cloud.style.height = "16px";

//         const label = document.createElement("span");
//         label.className = "label";
//         label.innerText = "Cloud";
//         label.style.left = (pos.cloud[0] + 20) + "px";
//         label.style.top = (pos.cloud[1] - 5) + "px";

//         canvas.appendChild(cloud);
//         canvas.appendChild(label);
//     }
// }


// // ---- Line Rendering Helper ----
// function drawLine(parent, start, end, color) {
//     const line = document.createElement("div");
//     line.className = "line";

//     const dx = end[0] - start[0];
//     const dy = end[1] - start[1];
//     const length = Math.sqrt(dx * dx + dy * dy);

//     line.style.width = length + "px";
//     line.style.left = start[0] + "px";
//     line.style.top = start[1] + "px";
//     line.style.transform = `rotate(${Math.atan2(dy, dx)}rad)`;
//     line.style.background = color;
//     parent.appendChild(line);
// }


// });

document.addEventListener("DOMContentLoaded", () => {

    const form = document.getElementById("simulationForm");
    const resultsSection = document.getElementById("simulationResults");

    let latencyBarChart, energyBarChart, qoeBarChart;

    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        const btn = form.querySelector("button[type='submit']");
        btn.disabled = true;
        btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Running...`;

        const payload = {
            uavCount: Number(document.getElementById("uavCount").value),
            userCount: Number(document.getElementById("userCount").value),
            bandwidth: Number(document.getElementById("bandwidth").value),
            taskSize: Number(document.getElementById("taskSize").value),
            cycles: Number(document.getElementById("cycles").value),
            areaSize: Number(document.getElementById("areaSize").value),
            uavRange: Number(document.getElementById("uavRange").value),
            simSteps: Number(document.getElementById("simSteps").value),
            userCPU: Number(document.getElementById("userCPU").value),
            uavCPU: Number(document.getElementById("uavCPU").value),
            cloudCPU: Number(document.getElementById("cloudCPU").value),
            kappaMU: Number(document.getElementById("kappaMU").value),
            kappaUAV: Number(document.getElementById("kappaUAV").value),
            uavBattery: Number(document.getElementById("uavBattery").value)
        };

        try {
            const response = await fetch("/result", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                throw new Error(await response.text());
            }

            const result = await response.json();
            updateResults(result);
            drawEnvironment(result);
            resultsSection.style.display = "block";

        } catch (err) {
            alert(`❌ Simulation Failed: ${err.message}`);
        }

        btn.disabled = false;
        btn.innerHTML = "▶ Run Simulation";
    });

    const avg = arr => arr.reduce((a,b)=>a+b,0) / arr.length;

    function updateResults(data){
        document.getElementById("successRate").textContent = `${(avg(data.Hybrid.QoE) * 100).toFixed(1)}%`;
        document.getElementById("avgLatency").textContent = `${avg(data.Hybrid.Latency).toFixed(2)}ms`;
        document.getElementById("energyUsage").textContent = `${avg(data.Hybrid.Energy).toFixed(2)} J`;
        document.getElementById("qoeScore").textContent = avg(data.Hybrid.QoE).toFixed(2);

        drawCharts(data);
    }

    function drawCharts(data){

        [latencyBarChart, energyBarChart, qoeBarChart]?.forEach(c=>c?.destroy());

        latencyBarChart = new Chart(document.getElementById("latencyChart"), {
            type:"bar",
            data:{
                labels:["DQN","AGSP","Hybrid"],
                datasets:[{
                    label:"Latency (ms)",
                    data:[avg(data.DQN.Latency), avg(data.AGSP.Latency), avg(data.Hybrid.Latency)],
                    backgroundColor:["#4361ee","#f59e0b","#10b981"]
                }]
            },
            options:{responsive:true}
        });

        energyBarChart = new Chart(document.getElementById("energyChart"), {
            type:"bar",
            data:{
                labels:["DQN","AGSP","Hybrid"],
                datasets:[{
                    label:"Energy (J)",
                    data:[avg(data.DQN.Energy), avg(data.AGSP.Energy), avg(data.Hybrid.Energy)],
                    backgroundColor:["#ef4444","#f59e0b","#10b981"]
                }]
            },
            options:{responsive:true}
        });

        qoeBarChart = new Chart(document.getElementById("qoeChart"), {
            type:"bar",
            data:{
                labels:["DQN","AGSP","Hybrid"],
                datasets:[{
                    label:"QoE",
                    data:[avg(data.DQN.QoE), avg(data.AGSP.QoE), avg(data.Hybrid.QoE)],
                    backgroundColor:["#4361ee","#f59e0b","#10b981"]
                }]
            },
            options:{responsive:true}
        });
    }


    //-----------------------------------------
    //         🚁 ENVIRONMENT VISUALIZER
    //-----------------------------------------
    
    let scale = 1, originX = 0, originY = 0, isDragging = false, startX, startY;

    function drawEnvironment(data) {
        const canvas = document.getElementById("uavEnvironment");
        canvas.innerHTML = "";

        if (!data.positions) {
            canvas.innerHTML = "<p style='padding:20px;text-align:center;'>No visualization data</p>";
            return;
        }

        let wrapper = document.createElement("div");
        wrapper.id = "envWrapper";
        wrapper.style.position = "absolute";
        canvas.appendChild(wrapper);

        const SCALE = 0.5;
        const bestAlgo = ["Hybrid", "DQN", "AGSP"].find(a => data[a]?.Offloading) || "Hybrid";
        const actions = data[bestAlgo]?.Offloading;
        const bestAction = actions?.at(-1);

        if (!bestAction) {
            canvas.innerHTML = "<p>No offloading behavior available</p>";
            return;
        }

        const pos = data.positions;
        const radius = Number(document.getElementById("uavRange").value) * SCALE;
        const uavColors = ["#6a0dad", "#1e40af", "#047857", "#fb923c", "#8b5cf6"];

        // UAV coverage circles
        pos.uavs.forEach((u, idx) => {
            const circle = document.createElement("div");
            circle.className = "uavRangeCircle";
            circle.style.width = radius*2+"px";
            circle.style.height = radius*2+"px";
            circle.style.left = (u[0]*SCALE-radius)+"px";
            circle.style.top = (u[1]*SCALE-radius)+"px";
            circle.style.borderColor = uavColors[idx % uavColors.length];
            wrapper.appendChild(circle);
        });

        // Users & links
        pos.users.forEach((user, i) => {
            const dot = document.createElement("div");
            dot.className = "userNode";
            dot.style.left = user[0]*SCALE + "px";
            dot.style.top = user[1]*SCALE + "px";
            wrapper.appendChild(dot);

            const action = bestAction[i];

            if (action === 0) {
                dot.style.background = "gray";
            } 
            else if (action > 0 && action <= pos.uavs.length) {
                const color = uavColors[action-1];
                dot.style.background = color;
                drawLine(wrapper, scalePoint(user), scalePoint(pos.uavs[action-1]), color);
            }
            else {
                dot.style.background = "red";
                drawLine(wrapper, scalePoint(user), scalePoint(pos.cloud), "red");
            }
        });

        // UAV nodes
        pos.uavs.forEach((u, idx) => {
            const dot = document.createElement("div");
            dot.className = "uavNode";
            dot.style.background = uavColors[idx];
            dot.style.left = u[0]*SCALE + "px";
            dot.style.top = u[1]*SCALE + "px";
            wrapper.appendChild(dot);

            const label = document.createElement("span");
            label.className = "label";
            label.innerText = `UAV${idx+1}`;
            label.style.left = u[0]*SCALE+20+"px";
            label.style.top = u[1]*SCALE-10+"px";
            wrapper.appendChild(label);
        });

        // Cloud
        const cloud = document.createElement("div");
        cloud.className = "uavNode";
        cloud.style.background = "red";
        cloud.style.borderRadius="0px";
        cloud.style.width="18px";
        cloud.style.height="18px";
        cloud.style.left = pos.cloud[0]*SCALE+"px";
        cloud.style.top = pos.cloud[1]*SCALE+"px";
        wrapper.appendChild(cloud);

        const cloudLabel = document.createElement("span");
        cloudLabel.className="label";
        cloudLabel.innerText="Cloud";
        cloudLabel.style.left=pos.cloud[0]*SCALE+20+"px";
        cloudLabel.style.top=pos.cloud[1]*SCALE+"px";
        wrapper.appendChild(cloudLabel);

        enableZoomPan(canvas, wrapper);
    }


    function scalePoint(pt) {
        return [pt[0]*0.5, pt[1]*0.5];
    }

    function drawLine(parent, start, end, color) {
        const line = document.createElement("div");
        line.className = "line";

        const dx=end[0]-start[0], dy=end[1]-start[1];
        const length=Math.sqrt(dx*dx+dy*dy);

        line.style.width=length+"px";
        line.style.left=start[0]+"px";
        line.style.top=start[1]+"px";
        line.style.transform=`rotate(${Math.atan2(dy,dx)}rad)`;
        line.style.background=color;
        parent.appendChild(line);
    }


    //-----------------------------------------
    //            🔍 ZOOM + PAN SYSTEM
    //-----------------------------------------
    function enableZoomPan(canvas, wrapper){

        scale = 1;
        originX = 0;
        originY = 0;
        wrapper.style.transform = `translate(0px,0px) scale(1)`;

        canvas.onwheel = (e)=> {
            e.preventDefault();
            const zoom = (e.deltaY < 0) ? 0.1 : -0.1;
            scale = Math.max(0.4, Math.min(3, scale + zoom));
            wrapper.style.transform = `translate(${originX}px,${originY}px) scale(${scale})`;
        };

        canvas.onmousedown = (e)=> {
            isDragging = true;
            startX = e.clientX - originX;
            startY = e.clientY - originY;
        };

        canvas.onmousemove = (e)=> {
            if(!isDragging) return;
            originX = e.clientX - startX;
            originY = e.clientY - startY;
            wrapper.style.transform = `translate(${originX}px,${originY}px) scale(${scale})`;
        };

        canvas.onmouseup = ()=> isDragging=false;
        canvas.onmouseleave = ()=> isDragging=false;
    }

    window.resetView = function(){
        scale=1; originX=0; originY=0;
        document.getElementById("envWrapper").style.transform = `translate(0px,0px) scale(1)`;
    };

});

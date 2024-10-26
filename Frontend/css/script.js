function addTask() {
    const taskInput = document.getElementById("taskInput");
    const taskText = taskInput.value.trim();
    if (taskText === "") return;
  
    const taskList = document.getElementById("taskList");
  
    const newTask = document.createElement("li");
    newTask.innerHTML = `
      <span>${taskText}</span>
      <button onclick="removeTask(this)">Remove</button>
      <button onclick="toggleComplete(this)">Complete</button>
    `;
  
    taskList.appendChild(newTask);
    taskInput.value = "";
  }
  
  function removeTask(button) {
    const task = button.parentElement;
    task.remove();
  }
  
  function toggleComplete(button) {
    const task = button.parentElement;
    task.classList.toggle("completed");
  }
  
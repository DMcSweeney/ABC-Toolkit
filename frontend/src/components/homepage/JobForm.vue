<script>
import axios from 'axios';


export default {
    name: 'JobForm',
    data() {
        return {
            project:'',
            csvFile: [],
        }
    },
    methods: {
        SubmitJob() {
            console.log('Submit form');
        },
        hasWhiteSpace(s) {
        return s.indexOf(' ') >= 0;
        },
        async handleFileUpload(event) {


            this.csvFile = event.target.files[0]
            console.log(this.csvFile['name'])
            // Check that a CSV file was uploaded
            if (this.csvFile['type'] == 'text/csv') {
                // Proceed with upload

                this.project = this.$refs.project_name.value;
                if (this.project == '') {
                    alert('Project name cannot be an empty')
                } else if (this.hasWhiteSpace(this.project)) {
                    alert('Project name cannot contain spaces!')
                } else{
                    console.log(`Uploading file to project: ${this.project}`)
                    let formData = new FormData();
                    formData.append('projectName', this.project);
                    formData.append('file', this.csvFile);

                    const url = `${import.meta.env.VITE_BACKEND_URI}/api/jobs/submit_jobs_from_csv`

                    let config = {
                        onUploadProgress: (progressEvent) => {
                            let percentCompleted = (100*progressEvent.loaded)/progressEvent.total;
                            console.log(percentCompleted);
                        }
                    }
                    await axios.post(url,
                     formData, config, {headers: {'Content-Type': 'multipart/form-data'}}
                    )
                    .then(() => {
                        console.log('I did it!');
                    })
                    .catch((err) => {
                        console.log("I didn't do it :(");
                        console.log(err);
                    })
                    // Maybe display summary of tasks that have been set (colnames and rows?)
                    // Show upload progress and 

                    // Open jobs in new tab 

                }
                
            } else{
            
                alert("Please upload a csv file!")
            
            }
        }
    }
}

</script>

<template>



<div class="flex m-auto py-5 w-full">
    <p class="text-stone-200 text-4xl align-center mx-auto"> Submit jobs </p>
</div>

<div class="h-screen">
<!-- Background -->
<div class="m-auto bg-zinc-900 h-1/4 w-1/2 border shadow shadow-black border-black p-3 flex-1 rounded">

<!-- Project name -->
    <div class="flex w-full mx-auto justify-center py-5">
        <input class="rounded text-xl px-2 bg-white h-10 w-1/2" type="text" :value=project placeholder="Project name" ref='project_name' required>
        <label class=" mx-4 my-auto bg-black hover:border hover:border-white hover:cursor-pointer hover:bg-zinc-800 rounded h-10 text-green-500 font-bold w-1/4 content-center align-center text-xl btn text-center" for="file-input"> Upload CSV</label>
        <input 
        ref="csvFile"
        id="file-input"
        type="file"
        @change="handleFileUpload"
        accept="text/csv"
        capture required hidden
        />
     </div>
    <!-- Upload CSV -->
    <!-- <div class="flex grid grid-cols-3">
        <div></div>
        <div class="content-center"> <input class="rounded text-zinc-950" type="file" :value=project  required>  </div>
        <div></div>
    </div> -->


    <!-- Settings -->

    <!-- Submit -->
        
</div>
</div>


</template>


<style scoped>

</style>

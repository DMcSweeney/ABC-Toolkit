<template>
    <div class="w-full p-8">
      <div class="container text-center text-stone-200 text-xl m-auto">
        <h2>Please enter password to access this page.</h2>
        <form v-on:submit.prevent="validateBeforeSubmit">
            <div class="form-group text-left">
            <input class="form-control password-field text-sm m-auto text-zinc-900 ml-3" type="password" name="password" v-model.trim="password">
            <span class="error help-block" ></span>
            <button class="text-sm rounded ml-3 p-2 bg-stone-200 text-stone-200 border-white hover:border hover:border-blue hover:text-blue bg-indigo-700"type="submit">Submit</button>
            </div>
            <div class="text-danger" v-if="error"><p>Incorrect password.</p></div>
            
        </form>
      </div>
    </div>
  </template>
  
  <script>
  import storageHelper from 'storage-helper'
  import router from '@/router';
  export default {
    data () {
      return {
        error: null,
        password: null,
      }
    },
    methods: {
      validateBeforeSubmit () {
        console.log(this.password)

        if (this.password === 'bodycomp') {
          this.error = false
          storageHelper.setItem('user-password', this.password)
          router.push('/')
        } else {
          this.error = true
        }
      }
    }
  }
  </script>